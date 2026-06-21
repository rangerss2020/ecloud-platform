from django.contrib import admin
from .models import AgentProfile, CommissionRecord

@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'level', 'commission_rate', 'total_commission', 'member_count', 'parent_agent', 'created_at']
    list_filter = ['level', 'created_at']
    search_fields = ['user__username']
    list_editable = ['commission_rate']

@admin.register(CommissionRecord)
class CommissionRecordAdmin(admin.ModelAdmin):
    list_display = ['agent', 'from_user', 'source_type', 'order_amount', 'commission_rate', 'commission_amount', 'status', 'created_at']
    list_filter = ['status', 'source_type', 'created_at']
    search_fields = ['agent__user__username', 'from_user__username']
    ordering = ['-created_at']
