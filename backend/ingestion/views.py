"""
Ingestion upload endpoint.
POST /api/ingestion/upload/  — accepts multipart file + source_id
Creates: IngestionJob → RawRecord (per row) → EmissionRecord (per valid row)
Deduplicates by SHA-256 file hash at the job level.
"""

import hashlib
import os
from datetime import datetime, timezone

from django.conf import settings
from django.db import models
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sources.models import DataSource, IngestionJob
from records.models import RawRecord, EmissionRecord
from factors.models import EmissionFactor, UnitConversion
from audit.models import AuditEvent

from .parsers.sap import parse_sap_csv
from .parsers.utility import parse_utility_csv
from .parsers.travel import parse_travel_csv


PARSER_MAP = {
    DataSource.SourceType.SAP_FLAT_FILE: parse_sap_csv,
    DataSource.SourceType.UTILITY_CSV: parse_utility_csv,
    DataSource.SourceType.TRAVEL_CSV: parse_travel_csv,
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _lookup_emission_factor(activity: str, region: str = "") -> EmissionFactor | None:
    """
    Find the most recent active emission factor for an activity.
    Falls back to no-region match if region-specific factor not found.
    """
    from django.utils import timezone as tz
    today = tz.now().date()
    qs = EmissionFactor.objects.filter(
        activity=activity,
        valid_from__lte=today,
    ).filter(
        models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=today)
    )
    if region:
        factor = qs.filter(region=region).first()
        if factor:
            return factor
    return qs.filter(region="").first() or qs.first()


def _apply_unit_conversion(quantity, from_unit: str, to_unit: str):
    """Convert quantity using UnitConversion table. Returns quantity unchanged if no conversion found."""
    if from_unit == to_unit:
        return quantity
    try:
        conv = UnitConversion.objects.get(from_unit=from_unit, to_unit=to_unit)
        return quantity * conv.factor
    except UnitConversion.DoesNotExist:
        return quantity


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_view(request):
    """
    POST /api/ingestion/upload/
    Form data: file (CSV), source_id (UUID)
    """
    file_obj = request.FILES.get('file')
    source_id = request.data.get('source_id')

    if not file_obj:
        return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
    if not source_id:
        return Response({'error': 'source_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Validate source belongs to org
    try:
        data_source = DataSource.objects.get(id=source_id, org=request.org)
    except DataSource.DoesNotExist:
        return Response({'error': 'Data source not found.'}, status=status.HTTP_404_NOT_FOUND)

    file_bytes = file_obj.read()
    file_hash = _sha256(file_bytes)

    # Deduplication: reject exact re-uploads
    duplicate = IngestionJob.objects.filter(
        data_source=data_source,
        file_hash=file_hash
    ).first()
    if duplicate:
        return Response({
            'error': f'This file has already been uploaded (Job ID: {duplicate.id}).',
            'existing_job_id': str(duplicate.id),
        }, status=status.HTTP_409_CONFLICT)

    # Save file to media storage
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', str(request.org.id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{file_hash}_{file_obj.name}")
    with open(file_path, 'wb') as f:
        f.write(file_bytes)
    relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)

    # Create IngestionJob
    job = IngestionJob.objects.create(
        data_source=data_source,
        org=request.org,
        triggered_by=request.user,
        status=IngestionJob.Status.PROCESSING,
        raw_file_path=relative_path,
        file_hash=file_hash,
        original_filename=file_obj.name,
        started_at=datetime.now(timezone.utc),
    )

    AuditEvent.objects.create(
        org=request.org,
        actor=request.user,
        event_type='JOB_STARTED',
        object_type='IngestionJob',
        object_id=str(job.id),
        payload={'source': data_source.display_name, 'filename': file_obj.name},
    )

    # Parse file
    try:
        file_content = file_bytes.decode('utf-8-sig')  # handle BOM from Excel exports
    except UnicodeDecodeError:
        file_content = file_bytes.decode('latin-1')

    parser_fn = PARSER_MAP.get(data_source.source_type)
    if not parser_fn:
        job.status = IngestionJob.Status.FAILED
        job.save()
        return Response({'error': f'No parser for source type {data_source.source_type}'}, status=400)

    try:
        parsed_rows = parser_fn(file_content, data_source.config)
    except Exception as e:
        job.status = IngestionJob.Status.FAILED
        job.error_summary = [{'error': str(e)}]
        job.completed_at = datetime.now(timezone.utc)
        job.save()
        return Response({'error': f'Parse failed: {e}'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Persist results
    row_count_raw = len(parsed_rows)
    row_count_ok = 0
    row_count_failed = 0
    error_summary = []

    for row in parsed_rows:
        row_status = row['status']
        parse_status_map = {
            'ok': RawRecord.ParseStatus.OK,
            'error': RawRecord.ParseStatus.PARSE_ERROR,
            'skipped': RawRecord.ParseStatus.SKIPPED,
        }

        raw_record = RawRecord.objects.create(
            ingestion_job=job,
            org=request.org,
            row_number=row['row_number'],
            raw_data=row['raw_data'],
            parse_status=parse_status_map.get(row_status, RawRecord.ParseStatus.PARSE_ERROR),
            parse_errors=row.get('errors', []),
        )

        if row_status != 'ok':
            if row_status == 'error':
                row_count_failed += 1
                error_summary.append({
                    'row': row['row_number'],
                    'errors': row.get('errors', []),
                })
            continue

        row_count_ok += 1

        # Look up emission factor
        activity = row.get('activity', '')
        region = row.get('scope2_method', '') or row.get('country', '')
        emission_factor = _lookup_emission_factor(activity, region)

        # Compute co2e_kg if factor found
        co2e_kg = None
        if emission_factor and row.get('quantity_normalized'):
            co2e_kg = row['quantity_normalized'] * emission_factor.factor_kg_co2e

        EmissionRecord.objects.create(
            org=request.org,
            raw_record=raw_record,
            data_source=data_source,
            scope=row['scope'],
            category=row['category'],
            activity_description=row['activity_description'],
            period_start=row['period_start'],
            period_end=row['period_end'],
            raw_quantity=row['raw_quantity'],
            raw_unit=row['raw_unit'],
            quantity_normalized=row['quantity_normalized'],
            unit_normalized=row['unit_normalized'],
            co2e_kg=co2e_kg,
            emission_factor=emission_factor,
            review_status=EmissionRecord.ReviewStatus.PENDING,
        )

    # Update job
    job.status = IngestionJob.Status.COMPLETED
    job.row_count_raw = row_count_raw
    job.row_count_ok = row_count_ok
    job.row_count_failed = row_count_failed
    job.error_summary = error_summary
    job.completed_at = datetime.now(timezone.utc)
    job.save()

    AuditEvent.objects.create(
        org=request.org,
        actor=request.user,
        event_type='JOB_COMPLETED',
        object_type='IngestionJob',
        object_id=str(job.id),
        payload={
            'row_count_raw': row_count_raw,
            'row_count_ok': row_count_ok,
            'row_count_failed': row_count_failed,
        },
    )

    return Response({
        'job_id': str(job.id),
        'status': job.status,
        'row_count_raw': row_count_raw,
        'row_count_ok': row_count_ok,
        'row_count_failed': row_count_failed,
        'error_summary': error_summary,
    }, status=status.HTTP_201_CREATED)
