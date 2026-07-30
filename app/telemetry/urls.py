from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PayloadIngestView,
    DeviceViewSet,
    DeviceHealthConfigViewSet,
)

app_name = 'telemetry'

router = DefaultRouter()
router.register(r'devices', DeviceViewSet, basename='device')
router.register(r'health-configs', DeviceHealthConfigViewSet, basename='health-config')

urlpatterns = [
    path('', PayloadIngestView.as_view(), name='payload-ingest'),
    path('', include(router.urls)),
]
