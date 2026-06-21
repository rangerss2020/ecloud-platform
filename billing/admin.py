from django.contrib import admin
from .models import PricingRule, RechargeOrder, Transaction, SystemConfig, RedeemCode

@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ['api_model', 'bill_type', 'unit_price', 'min_level', 'created_at']
    list_filter = ['bill_type', 'min_level']
    search_fields = ['api_model__name']

@admin.register(RechargeOrder)
class RechargeOrderAdmin(admin.ModelAdmin):
    list_display = ['order_no', 'user', 'amount', 'pay_method', 'status', 'created_at']
    list_filter = ['status', 'pay_method', 'created_at']
    search_fields = ['order_no', 'user__username']
    ordering = ['-created_at']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'type', 'amount', 'balance_after', 'description', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['user__username', 'description', 'related_order']
    ordering = ['-created_at']

@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'description', 'updated_at']
    search_fields = ['key', 'description']
    list_editable = ['value']


@admin.register(RedeemCode)
class RedeemCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'amount', 'batch_no', 'is_used', 'used_by', 'used_at', 'created_at']
    list_filter = ['is_used', 'created_at']
    search_fields = ['code', 'batch_no']
