from django.contrib import admin

from .models import Device, Payload, DeviceHealthConfig, DeviceFailure


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('dev_eui', 'latest_status', 'updated_at', 'created_at')
    list_filter = ('latest_status',)
    # Load-bearing: PayloadAdmin.autocomplete_fields requires it.
    search_fields = ('dev_eui',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Payload)
class PayloadAdmin(admin.ModelAdmin):
    list_display = (
        'device',
        'f_cnt',
        'status',
        'decoded_hex',
        'received_at',
        'created_at',
    )
    list_filter = ('status',)
    search_fields = ('device__dev_eui',)
    # Rendering `device` in list_display and __str__ would otherwise be an N+1.
    list_select_related = ('device',)
    # A plain FK dropdown renders every device on the add form.
    autocomplete_fields = ('device',)
    readonly_fields = ('created_at',)


@admin.register(DeviceHealthConfig)
class DeviceHealthConfigAdmin(admin.ModelAdmin):
    list_display = (
        'device',
        'inactivity_window_seconds',
        'temp_min',
        'temp_max',
        'humidity_min',
        'humidity_max',
        'expected_frequency_seconds',
        'updated_at',
    )
    list_filter = ('updated_at',)
    search_fields = ('device__dev_eui',)
    autocomplete_fields = ('device',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Device', {'fields': ('device',)}),
        ('Thresholds', {
            'fields': (
                'inactivity_window_seconds',
                'expected_frequency_seconds',
            )
        }),
        ('Temperature', {'fields': ('temp_min', 'temp_max')}),
        ('Humidity', {'fields': ('humidity_min', 'humidity_max')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(DeviceFailure)
class DeviceFailureAdmin(admin.ModelAdmin):
    list_display = ('device', 'failure_type', 'detected_at', 'resolved_at')
    list_filter = ('failure_type', 'resolved_at')
    search_fields = ('device__dev_eui',)
    autocomplete_fields = ('device',)
    readonly_fields = ('detected_at', 'device', 'failure_type')
    fieldsets = (
        ('Device', {'fields': ('device',)}),
        ('Failure', {'fields': ('failure_type', 'details')}),
        ('Timeline', {'fields': ('detected_at', 'resolved_at')}),
    )
