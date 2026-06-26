from django.db import models
from django.utils import timezone
from django.conf import settings


class PricingRule(models.Model):
    BILL_TYPE_CHOICES = (
        ('per_call', '按次计费'),
        ('per_unit', '按量计费'),
        ('free', '免费'),
    )

    api_model = models.ForeignKey(
        'apimodels.ApiModel', on_delete=models.CASCADE, related_name='pricing_rules',
        verbose_name='API模型'
    )
    bill_type = models.CharField(max_length=10, choices=BILL_TYPE_CHOICES, default='per_call', verbose_name='计费方式')
    unit_price = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='单价(元)')
    min_level = models.IntegerField(default=1, verbose_name='最低会员等级')
    description = models.CharField(max_length=255, blank=True, verbose_name='规则说明')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'pricing_rules'
        verbose_name = '计费规则'
        verbose_name_plural = verbose_name


class RechargeOrder(models.Model):
    STATUS_CHOICES = (
        ('pending', '待支付'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('cancelled', '已取消'),
    )
    PAY_METHODS = (
        ('alipay', '支付宝'),
        ('wechat', '微信支付'),
    )

    order_no = models.CharField(max_length=32, unique=True, verbose_name='订单号')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='用户')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='充值金额(元)')
    pay_method = models.CharField(max_length=10, choices=PAY_METHODS, default='alipay', verbose_name='支付方式')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'recharge_orders'
        verbose_name = '充值订单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class Transaction(models.Model):
    TYPE_CHOICES = (
        ('recharge', '充值'),
        ('consume', '消费'),
        ('commission', '佣金'),
        ('refund', '退款'),
        ('adjust', '调整'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='用户')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name='交易类型')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='金额(元)')
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='交易后余额')
    description = models.CharField(max_length=255, verbose_name='交易描述')
    related_order = models.CharField(max_length=32, blank=True, verbose_name='关联订单号')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='交易时间')

    class Meta:
        db_table = 'transactions'
        verbose_name = '交易记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class SystemConfig(models.Model):
    key = models.CharField(max_length=100, unique=True, verbose_name='配置键')
    value = models.TextField(verbose_name='配置值')
    description = models.CharField(max_length=255, blank=True, verbose_name='说明')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'system_configs'
        verbose_name = '系统配置'
        verbose_name_plural = verbose_name

    @classmethod
    def get(cls, key, default=''):
        obj = cls.objects.filter(key=key).first()
        return obj.value if obj else default

    @classmethod
    def set(cls, key, value, description=''):
        cls.objects.update_or_create(key=key, defaults={'value': value, 'description': description})


class Package(models.Model):
    STATUS_CHOICES = (('enabled', '上架'), ('disabled', '下架'))
    DURATION_TYPES = (('day', '天'), ('month', '月'), ('year', '年'), ('forever', '永久'))

    name = models.CharField(max_length=100, verbose_name='套餐名称')
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='价格(元)')
    description = models.TextField(blank=True, verbose_name='描述')
    call_limit = models.IntegerField(default=0, verbose_name='调用次数限制(0=不限)')
    token_limit = models.BigIntegerField(default=0, verbose_name='Token量限制(0=不限)')
    duration_type = models.CharField(max_length=10, choices=DURATION_TYPES, default='month', verbose_name='期限类型')
    duration_value = models.IntegerField(default=1, verbose_name='期限值')
    model_restrict = models.BooleanField(default=False, verbose_name='限制模型')
    model_ids = models.JSONField(default=list, blank=True, verbose_name='可用模型ID列表')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='enabled', verbose_name='状态')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'packages'
        verbose_name = '套餐'
        verbose_name_plural = verbose_name
        ordering = ['sort_order']

    def __str__(self):
        return self.name


class UserPackage(models.Model):
    STATUS_CHOICES = (('active', '使用中'), ('expired', '已过期'), ('used_up', '已用完'))

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='用户')
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, verbose_name='套餐')
    start_date = models.DateTimeField(default=timezone.now, verbose_name='生效时间')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='到期时间')
    calls_used = models.IntegerField(default=0, verbose_name='已用调用次数')
    tokens_used = models.BigIntegerField(default=0, verbose_name='已用Token量')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', verbose_name='状态')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='购买时间')

    class Meta:
        db_table = 'user_packages'
        verbose_name = '用户套餐'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class RedeemCode(models.Model):
    code = models.CharField(max_length=32, unique=True, verbose_name='兑换码')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='金额(元)')
    is_used = models.BooleanField(default=False, verbose_name='已使用')
    used_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='使用者')
    used_at = models.DateTimeField(null=True, blank=True, verbose_name='使用时间')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    batch_no = models.CharField(max_length=32, blank=True, verbose_name='批次号')

    class Meta:
        db_table = 'redeem_codes'
        verbose_name = '兑换码'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
