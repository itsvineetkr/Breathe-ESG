from django.utils import timezone
from django.db.models import Sum, Count, Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import EmissionRecord
from .serializers import (
    EmissionRecordSerializer, EmissionRecordDetailSerializer, ReviewActionSerializer
)
from apps.audit.models import AuditLog


class EmissionPaginator(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_records(request):
    """
    GET /api/emissions/records/
    Filters: status, scope, category, source, is_flagged, date_from, date_to
    """
    profile = request.user.profile
    qs = EmissionRecord.objects.filter(organization=profile.organization).select_related('source', 'reviewed_by__user')

    # Filters
    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    scope = request.query_params.get('scope')
    if scope:
        qs = qs.filter(scope=scope)

    category = request.query_params.get('category')
    if category:
        qs = qs.filter(category=category)

    source_id = request.query_params.get('source')
    if source_id:
        qs = qs.filter(source_id=source_id)

    is_flagged = request.query_params.get('is_flagged')
    if is_flagged is not None:
        qs = qs.filter(is_flagged=(is_flagged.lower() == 'true'))

    date_from = request.query_params.get('date_from')
    if date_from:
        qs = qs.filter(activity_date__gte=date_from)

    date_to = request.query_params.get('date_to')
    if date_to:
        qs = qs.filter(activity_date__lte=date_to)

    paginator = EmissionPaginator()
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(EmissionRecordSerializer(page, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def record_detail(request, pk):
    """GET /api/emissions/records/<pk>/ — full detail including source_row_data."""
    profile = request.user.profile
    try:
        record = EmissionRecord.objects.get(id=pk, organization=profile.organization)
    except EmissionRecord.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(EmissionRecordDetailSerializer(record).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def review_record(request, pk):
    """
    POST /api/emissions/records/<pk>/review/
    Body: { action, notes, scope, category, flag_reason }

    State machine:
    pending_review → approve → approved
    pending_review → reject  → rejected
    approved → reject → rejected (re-review)
    any → flag/unflag (orthogonal to status)
    any → add_note (always allowed)
    any → edit_scope (reclassify material)
    """
    profile = request.user.profile
    try:
        record = EmissionRecord.objects.get(id=pk, organization=profile.organization)
    except EmissionRecord.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ReviewActionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    action = serializer.validated_data['action']
    notes = serializer.validated_data.get('notes', '')

    old_values = {
        'status': record.status,
        'is_flagged': record.is_flagged,
        'scope': record.scope,
        'category': record.category,
        'analyst_notes': record.analyst_notes,
    }

    if action == 'approve':
        record.status = EmissionRecord.STATUS_APPROVED
        record.reviewed_by = profile
        record.reviewed_at = timezone.now()
        if notes:
            record.analyst_notes = notes

    elif action == 'reject':
        record.status = EmissionRecord.STATUS_REJECTED
        record.reviewed_by = profile
        record.reviewed_at = timezone.now()
        if notes:
            record.analyst_notes = notes

    elif action == 'flag':
        record.is_flagged = True
        reason = serializer.validated_data.get('flag_reason', notes)
        if reason and reason not in record.flag_reasons:
            record.flag_reasons = record.flag_reasons + [f"Manual flag: {reason}"]

    elif action == 'unflag':
        record.is_flagged = False

    elif action == 'add_note':
        if notes:
            record.analyst_notes = (record.analyst_notes + '\n' + notes).strip() if record.analyst_notes else notes

    elif action == 'edit_scope':
        new_scope = serializer.validated_data.get('scope')
        new_category = serializer.validated_data.get('category')
        if new_scope:
            record.scope = new_scope
        if new_category:
            record.category = new_category
        if notes:
            record.analyst_notes = (record.analyst_notes + '\n' + notes).strip() if record.analyst_notes else notes

    record.save()

    new_values = {
        'status': record.status,
        'is_flagged': record.is_flagged,
        'scope': record.scope,
        'category': record.category,
        'analyst_notes': record.analyst_notes,
    }

    # Map action to audit log action constant
    audit_action_map = {
        'approve': AuditLog.ACTION_APPROVE,
        'reject': AuditLog.ACTION_REJECT,
        'flag': AuditLog.ACTION_FLAG,
        'unflag': AuditLog.ACTION_UNFLAG,
        'add_note': AuditLog.ACTION_NOTE,
        'edit_scope': AuditLog.ACTION_SCOPE_CHANGE,
    }

    AuditLog.objects.create(
        organization=profile.organization,
        record=record,
        action=audit_action_map.get(action, AuditLog.ACTION_EDIT),
        old_values=old_values,
        new_values=new_values,
        user=profile,
        notes=notes,
    )

    return Response(EmissionRecordSerializer(record).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_review(request):
    """
    POST /api/emissions/records/bulk-review/
    Body: { record_ids: [...], action: 'approve'|'reject', notes: '...' }

    Batch approve or reject multiple records. Useful for clearing clean rows
    after reviewing a few samples from a dataset.
    """
    profile = request.user.profile
    record_ids = request.data.get('record_ids', [])
    action = request.data.get('action')
    notes = request.data.get('notes', '')

    if action not in ('approve', 'reject'):
        return Response({'detail': "action must be 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)

    records = EmissionRecord.objects.filter(
        id__in=record_ids, organization=profile.organization
    )

    now = timezone.now()
    new_status = EmissionRecord.STATUS_APPROVED if action == 'approve' else EmissionRecord.STATUS_REJECTED
    audit_action = AuditLog.ACTION_APPROVE if action == 'approve' else AuditLog.ACTION_REJECT

    audit_logs = []
    for record in records:
        old_status = record.status
        record.status = new_status
        record.reviewed_by = profile
        record.reviewed_at = now
        if notes:
            record.analyst_notes = notes
        audit_logs.append(AuditLog(
            organization=profile.organization,
            record=record,
            action=audit_action,
            old_values={'status': old_status},
            new_values={'status': new_status},
            user=profile,
            notes=notes,
        ))

    EmissionRecord.objects.bulk_update(records, ['status', 'reviewed_by', 'reviewed_at', 'analyst_notes'])
    AuditLog.objects.bulk_create(audit_logs)

    return Response({'updated': len(records)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reports(request):
    """
    GET /api/emissions/reports/
    Aggregate emissions for approved records.

    Returns:
    - Total CO2e by scope
    - Total CO2e by category
    - Total CO2e by source (dataset)
    - Total CO2e by month
    - Summary counts
    """
    profile = request.user.profile
    org = profile.organization

    base_qs = EmissionRecord.objects.filter(
        organization=org,
        status=EmissionRecord.STATUS_APPROVED,
        co2e_kg__isnull=False,
    )

    # Optional date filter
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from:
        base_qs = base_qs.filter(activity_date__gte=date_from)
    if date_to:
        base_qs = base_qs.filter(activity_date__lte=date_to)

    # By scope
    by_scope = list(
        base_qs.values('scope').annotate(total_co2e_kg=Sum('co2e_kg')).order_by('scope')
    )
    for row in by_scope:
        row['total_co2e_tonnes'] = row['total_co2e_kg'] / 1000.0 if row['total_co2e_kg'] else 0

    # By category
    by_category = list(
        base_qs.values('scope', 'category').annotate(
            total_co2e_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('scope', 'category')
    )
    for row in by_category:
        row['total_co2e_tonnes'] = row['total_co2e_kg'] / 1000.0 if row['total_co2e_kg'] else 0

    # By source (dataset)
    by_source = list(
        base_qs.values('source__id', 'source__name', 'source__source_type').annotate(
            total_co2e_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('-total_co2e_kg')
    )
    for row in by_source:
        row['total_co2e_tonnes'] = row['total_co2e_kg'] / 1000.0 if row['total_co2e_kg'] else 0

    # By month (for chart)
    from django.db.models.functions import TruncMonth
    by_month = list(
        base_qs.annotate(month=TruncMonth('activity_date'))
        .values('month', 'scope')
        .annotate(total_co2e_kg=Sum('co2e_kg'))
        .order_by('month', 'scope')
    )
    for row in by_month:
        row['month'] = row['month'].strftime('%Y-%m') if row['month'] else None
        row['total_co2e_tonnes'] = row['total_co2e_kg'] / 1000.0 if row['total_co2e_kg'] else 0

    # Status summary (all records, not just approved)
    all_records = EmissionRecord.objects.filter(organization=org)
    status_summary = {
        'total': all_records.count(),
        'pending_review': all_records.filter(status=EmissionRecord.STATUS_PENDING).count(),
        'approved': all_records.filter(status=EmissionRecord.STATUS_APPROVED).count(),
        'rejected': all_records.filter(status=EmissionRecord.STATUS_REJECTED).count(),
        'flagged': all_records.filter(is_flagged=True).count(),
    }

    total_co2e_kg = base_qs.aggregate(t=Sum('co2e_kg'))['t'] or 0

    return Response({
        'organization': org.name,
        'total_co2e_kg': total_co2e_kg,
        'total_co2e_tonnes': total_co2e_kg / 1000.0,
        'by_scope': by_scope,
        'by_category': by_category,
        'by_source': by_source,
        'by_month': by_month,
        'status_summary': status_summary,
    })
