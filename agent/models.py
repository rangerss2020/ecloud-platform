from django.db import models
from django.conf import settings
from django.utils import timezone


class AgentProfile(models.Model):
    LEVEL_CHOICES = (
        (1, '一级代理'),
        (2, '二级代理'),
        (3, '三级代理'),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='用户')
    level = models.IntegerField(choices=LEVEL_CHOICES, default=1, verbose_name='代理等级')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, verbose_name='佣金比例(%)')
    parent_agent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sub_agents', verbose_name='上级代理'
    )
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='累计佣金')
    member_count = models.IntegerField(default=0, verbose_name='下级会员数')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='成为代理时间')

    class Meta:
        db_table = 'agent_profiles'
        verbose_name = '代理信息'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} - L{self.level}代理"


class CommissionRecord(models.Model):
    STATUS_CHOICES = (
        ('pending', '待结算'),
        ('settled', '已结算'),
    )

    agent = models.ForeignKey(AgentProfile, on_delete=models.CASCADE, verbose_name='代理')
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='来源用户'
    )
    source_type = models.CharField(max_length=20, verbose_name='来源类型')
    order_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='订单金额')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='佣金比例(%)')
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='佣金金额')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='产生时间')
    settled_at = models.DateTimeField(null=True, blank=True, verbose_name='结算时间')

    class Meta:
        db_table = 'commission_records'
        verbose_name = '佣金记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class Withdrawal(models.Model):
    STATUS_CHOICES = (
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
    )

    agent = models.ForeignKey(AgentProfile, on_delete=models.CASCADE, verbose_name='代理')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='提现金额')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_withdrawals', verbose_name='审核人')
    review_remark = models.CharField(max_length=255, blank=True, verbose_name='审核备注')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='申请时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'withdrawals'
        verbose_name = '提现申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
