from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PayloadIngestView,
    DeviceViewSet,
    DeviceHealthConfigViewSet,
    DevicesSearchView,
    DeviceDetailView,
)

app_name = 'telemetry'

router = DefaultRouter()
router.register(r'devices', DeviceViewSet, basename='device')
router.register(r'health-configs', DeviceHealthConfigViewSet, basename='health-config')

urlpatterns = [
    path('', PayloadIngestView.as_view(), name='payload-ingest'),
    path('', include(router.urls)),
    path('devices/', DevicesSearchView.as_view(), name='devices-search'),
    path('devices/<int:device_id>/detail/', DeviceDetailView.as_view(), name='device-detail'),
]
