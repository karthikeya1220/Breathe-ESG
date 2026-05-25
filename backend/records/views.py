from datetime import datetime, timezone

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from audit.models import AuditEvent
from .models import EmissionRecord, AnalystReview
from .serializers import (
    EmissionRecordListSerializer,
    EmissionRecordDetailSerializer,
    ReviewActionSerializer,
)


class EmissionRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/records/           — paginated list, filterable by status/scope/source
    GET  /api/records/{id}/      — full detail with raw data side-by-side
    POST /api/records/{id}/review/ — approve / flag / reject
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = EmissionRecord.objects.filter(
            org=self.request.user.org
        ).select_related(
            'data_source', 'emission_factor', 'raw_record', 'locked_by'
        ).prefetch_related('reviews__reviewer')

        # Filters
        params = self.request.query_params
        if status_filter := params.get('status'):
            qs = qs.filter(review_status=status_filter.upper())
        if scope_filter := params.get('scope'):
            qs = qs.filter(scope=scope_filter.upper())
        if source_filter := params.get('source'):
            qs = qs.filter(data_source_id=source_filter)

        return qs.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EmissionRecordDetailSerializer
        return EmissionRecordListSerializer

    @action(detail=True, methods=['post'], url_path='review')
    def review(self, request, pk=None):
        """
        POST /api/records/{id}/review/
        Body: {"action": "APPROVED"|"FLAGGED"|"REJECTED", "comment": "..."}

        Enforces is_locked: a locked record raises 403.
        Approval sets is_locked=True and fires audit event.
        """
        record = self.get_object()

        if record.is_locked:
            return Response(
                {'error': 'This record is locked and cannot be modified.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_value = serializer.validated_data['action']
        comment = serializer.validated_data.get('comment', '')

        # Update EmissionRecord status
        record.review_status = action_value
        if action_value == AnalystReview.Action.APPROVED:
            record.is_locked = True
            record.locked_at = datetime.now(timezone.utc)
            record.locked_by = request.user
        record.save()

        # Append-only review event
        AnalystReview.objects.create(
            emission_record=record,
            org=request.user.org,
            reviewer=request.user,
            action=action_value,
            comment=comment,
        )

        # Audit trail
        AuditEvent.objects.create(
            org=request.user.org,
            actor=request.user,
            event_type=f'RECORD_{action_value}',
            object_type='EmissionRecord',
            object_id=str(record.id),
            payload={
                'action': action_value,
                'comment': comment,
                'reviewer': request.user.username,
            },
        )

        return Response(
            EmissionRecordDetailSerializer(record, context={'request': request}).data
        )
