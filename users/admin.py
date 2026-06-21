from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'role', 'balance', 'phone', 'api_key', 'parent_agent', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'is_staff', 'created_at']
    search_fields = ['username', 'email', 'phone', 'api_key']
    ordering = ['-created_at']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('平台信息', {'fields': ('role', 'balance', 'phone', 'avatar', 'api_key', 'api_secret', 'parent_agent')}),
    )
    readonly_fields = ['api_key', 'api_secret']
