from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import AuditLog
from .serializers import AuditLogSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_audit_logs(request):
    """
    GET /api/audit/logs/
    Admin-only: returns all audit events for this org.
    Analysts can only see their own.
    """
    profile = request.user.profile
    qs = AuditLog.objects.filter(organization=profile.organization).select_related(
        'user__user', 'record', 'datasource'
    )

    if not profile.is_admin:
        # Analysts see only their own actions
        qs = qs.filter(user=profile)

    # Filters
    action = request.query_params.get('action')
    if action:
        qs = qs.filter(action=action)

    record_id = request.query_params.get('record')
    if record_id:
        qs = qs.filter(record_id=record_id)

    paginator = PageNumberPagination()
    paginator.page_size = 100
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)
