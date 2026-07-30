from django.contrib import admin

from .models import Device, Payload


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
