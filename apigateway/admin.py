from django.contrib import admin
from .models import ApiRequestRecord, SensitiveWord

@admin.register(ApiRequestRecord)
class ApiRequestRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'api_model', 'request_method', 'cost', 'response_state', 'duration_ms', 'created_at']
    list_filter = ['status', 'response_state', 'request_method', 'created_at']
    search_fields = ['user__username', 'api_model__name', 'ip_address']
    ordering = ['-created_at']
    readonly_fields = ['user', 'api_model', 'request_method', 'request_url', 'request_params',
                       'response_data', 'response_state', 'cost', 'balance_before', 'balance_after',
                       'status', 'error_message', 'filter_hits', 'duration_ms', 'ip_address', 'created_at']


@admin.register(SensitiveWord)
class SensitiveWordAdmin(admin.ModelAdmin):
    list_display = ['word', 'level', 'replacement', 'category', 'enabled', 'created_at']
    list_filter = ['level', 'enabled', 'category']
    search_fields = ['word', 'category']
    list_editable = ['level', 'enabled']
