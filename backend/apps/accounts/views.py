from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserProfile, Organization
from .serializers import (
    RegisterSerializer, AddAnalystSerializer, MeSerializer,
    UserProfileSerializer, OrganizationSerializer
)


def _token_response(user, profile):
    """Issue JWT tokens and return alongside user profile."""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': MeSerializer(profile).data,
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Admin registration endpoint. Creates org + admin user atomically.
    POST /api/auth/register/
    """
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    profile = serializer.save()
    return Response(_token_response(profile.user, profile), status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    POST /api/auth/login/   { email, password }
    Returns JWT tokens + user profile.
    """
    from django.contrib.auth import authenticate
    email = request.data.get('email', '').lower()
    password = request.data.get('password', '')
    user = authenticate(request, username=email, password=password)
    if not user:
        return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return Response({'detail': 'No profile found for this user.'}, status=status.HTTP_403_FORBIDDEN)
    if not profile.is_active:
        return Response({'detail': 'Account is deactivated.'}, status=status.HTTP_403_FORBIDDEN)
    return Response(_token_response(user, profile))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """GET /api/auth/me/ — current user's profile."""
    return Response(MeSerializer(request.user.profile).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_analysts(request):
    """GET /api/auth/analysts/ — list all members of the org (admin only)."""
    profile = request.user.profile
    if not profile.is_admin:
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    members = UserProfile.objects.filter(organization=profile.organization).select_related('user')
    return Response(UserProfileSerializer(members, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_analyst(request):
    """POST /api/auth/analysts/ — admin creates an analyst in their org."""
    profile = request.user.profile
    if not profile.is_admin:
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    serializer = AddAnalystSerializer(data=request.data, context={'organization': profile.organization})
    serializer.is_valid(raise_exception=True)
    new_profile = serializer.save()
    return Response(UserProfileSerializer(new_profile).data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_analyst(request, analyst_id):
    """DELETE /api/auth/analysts/<id>/ — deactivate (not delete) an analyst."""
    profile = request.user.profile
    if not profile.is_admin:
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        target = UserProfile.objects.get(id=analyst_id, organization=profile.organization)
    except UserProfile.DoesNotExist:
        return Response({'detail': 'Analyst not found.'}, status=status.HTTP_404_NOT_FOUND)
    if target.is_admin:
        return Response({'detail': 'Cannot deactivate another admin.'}, status=status.HTTP_400_BAD_REQUEST)
    target.is_active = False
    target.save()
    return Response({'detail': 'Analyst deactivated.'})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_org(request):
    """PATCH /api/auth/org/ — update org settings (electricity factor, plant codes, field mappings)."""
    profile = request.user.profile
    if not profile.is_admin:
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    serializer = OrganizationSerializer(profile.organization, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)
