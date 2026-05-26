from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import DataSource
from .serializers import DataSourceSerializer, DataSourceUploadSerializer
from .pipeline import run_pipeline
from .parsers.sap import parse_sap_file
from .parsers.utility import parse_utility_file
from .parsers.travel import parse_travel_file
from apps.audit.models import AuditLog


PARSER_MAP = {
    DataSource.SOURCE_SAP: parse_sap_file,
    DataSource.SOURCE_UTILITY: parse_utility_file,
    DataSource.SOURCE_TRAVEL: parse_travel_file,
}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_file(request):
    """
    POST /api/ingestion/upload/
    Accepts multipart form: name, source_type, file, field_mapping_override (optional JSON).

    Steps:
    1. Save the DataSource record (raw file preserved).
    2. Run the appropriate parser on the file bytes.
    3. Run the normalization + emission factor pipeline.
    4. Return parse statistics.
    """
    profile = request.user.profile
    serializer = DataSourceUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    uploaded_file = serializer.validated_data['file']
    source_type = serializer.validated_data['source_type']

    # Save DataSource with raw file
    datasource = DataSource.objects.create(
        organization=profile.organization,
        source_type=source_type,
        name=serializer.validated_data['name'],
        raw_file=uploaded_file,
        original_filename=uploaded_file.name,
        uploaded_by=profile,
        status=DataSource.STATUS_PROCESSING,
        field_mapping_override=serializer.validated_data.get('field_mapping_override', {}),
    )

    # Log the upload
    AuditLog.objects.create(
        organization=profile.organization,
        datasource=datasource,
        action=AuditLog.ACTION_UPLOAD,
        new_values={'name': datasource.name, 'source_type': source_type, 'filename': uploaded_file.name},
        user=profile,
    )

    # Read file bytes
    uploaded_file.seek(0)
    file_bytes = uploaded_file.read()

    # Merge org-level field mapping overrides with per-upload overrides
    org_overrides = profile.organization.field_mapping_overrides.get(source_type, {})
    per_upload_overrides = datasource.field_mapping_override
    combined_overrides = {**org_overrides, **per_upload_overrides}

    # Parse
    parser_fn = PARSER_MAP[source_type]
    try:
        parsed_rows = parser_fn(file_bytes, org_field_overrides=combined_overrides)
    except Exception as e:
        datasource.status = DataSource.STATUS_FAILED
        datasource.parse_log = [{'row': 0, 'error': f"Parser crashed: {e}"}]
        datasource.save()
        return Response(
            {'detail': f"Parse failed: {e}"},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # Run normalization + DB save pipeline
    stats = run_pipeline(datasource, parsed_rows)

    # Log parse completion
    AuditLog.objects.create(
        organization=profile.organization,
        datasource=datasource,
        action=AuditLog.ACTION_PARSE_COMPLETE,
        new_values=stats,
        user=profile,
    )

    return Response({
        'datasource': DataSourceSerializer(datasource).data,
        'stats': stats,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_datasources(request):
    """GET /api/ingestion/sources/ — list all uploads for this org."""
    profile = request.user.profile
    qs = DataSource.objects.filter(organization=profile.organization)

    source_type = request.query_params.get('source_type')
    if source_type:
        qs = qs.filter(source_type=source_type)

    paginator = PageNumberPagination()
    paginator.page_size = 20
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(DataSourceSerializer(page, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def datasource_detail(request, pk):
    """GET /api/ingestion/sources/<pk>/ — detail + parse log."""
    profile = request.user.profile
    try:
        ds = DataSource.objects.get(id=pk, organization=profile.organization)
    except DataSource.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    data = DataSourceSerializer(ds).data
    data['parse_log'] = ds.parse_log
    return Response(data)
