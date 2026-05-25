from rest_framework import viewsets, permissions
from .models import DataSource, IngestionJob
from .serializers import DataSourceSerializer, IngestionJobSerializer


class DataSourceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DataSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DataSource.objects.filter(org=self.request.user.org)


class IngestionJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngestionJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return IngestionJob.objects.filter(org=self.request.user.org).select_related('data_source')
