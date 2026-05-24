from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework import viewsets, permissions
from .models import EmissionFactor
from rest_framework import serializers


class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = '__all__'


class EmissionFactorViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EmissionFactorSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = EmissionFactor.objects.all()


router = DefaultRouter()
router.register('emission-factors', EmissionFactorViewSet, basename='emission-factor')

urlpatterns = [path('', include(router.urls))]
