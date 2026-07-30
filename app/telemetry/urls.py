from django.urls import path

from .views import PayloadIngestView

app_name = 'telemetry'

urlpatterns = [
    path('', PayloadIngestView.as_view(), name='payload-ingest'),
]
