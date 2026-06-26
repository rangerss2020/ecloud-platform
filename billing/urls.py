from .views import billing_index, recharge, check_order_status, pay_callback, transaction_list, system_settings, payment_settings, redeem_code, manage_redeem_codes, manage_packages, buy_package, admin_transactions
from django.urls import path

urlpatterns = [
    path('', billing_index, name='billing_index'),
    path('recharge/', recharge, name='recharge'),
    path('check/<str:order_no>/', check_order_status, name='check_order'),
    path('callback/alipay/', pay_callback, {'provider': 'alipay'}, name='pay_callback_alipay'),
    path('callback/wechat/', pay_callback, {'provider': 'wechat'}, name='pay_callback_wechat'),
    path('transactions/', transaction_list, name='transaction_list'),
    path('settings/', system_settings, name='system_settings'),
    path('payment/', payment_settings, name='payment_settings'),
    path('redeem/', redeem_code, name='redeem_code'),
    path('admin/redeem-codes/', manage_redeem_codes, name='manage_redeem_codes'),
    path('admin/packages/', manage_packages, name='manage_packages'),
    path('admin/transactions/', admin_transactions, name='admin_transactions'),
    path('buy-package/<int:package_id>/', buy_package, name='buy_package'),
]
