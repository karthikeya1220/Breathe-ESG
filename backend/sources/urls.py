from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DataSourceViewSet, IngestionJobViewSet

router = DefaultRouter()
router.register('datasources', DataSourceViewSet, basename='datasource')
router.register('jobs', IngestionJobViewSet, basename='ingestion-job')

urlpatterns = [path('', include(router.urls))]
