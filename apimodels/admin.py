from django.contrib import admin
from .models import Channel, ApiModel, ApiParameter, ApiUsageLog


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'base_url', 'auth_type', 'status', 'sort_order']
    list_filter = ['status', 'auth_type']
    search_fields = ['name', 'code', 'access_key', 'api_key']


class ApiParameterInline(admin.TabularInline):
    model = ApiParameter
    extra = 1


@admin.register(ApiModel)
class ApiModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'channel', 'http_method', 'bill_type', 'price', 'unit_type', 'status', 'sort_order']
    list_filter = ['status', 'bill_type', 'http_method', 'channel']
    search_fields = ['name', 'code', 'description']
    inlines = [ApiParameterInline]
    list_editable = ['price', 'status', 'sort_order']


@admin.register(ApiUsageLog)
class ApiUsageLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'model', 'channel', 'cost', 'response_state', 'created_at']
    list_filter = ['response_state']
    search_fields = ['user__username', 'model__name']
    ordering = ['-created_at']
    readonly_fields = ['user', 'model', 'channel', 'request_params', 'response_data', 'cost', 'ip_address']
