from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
import secrets


class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', '管理员'),
        ('agent', '代理'),
        ('member', '会员'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member', verbose_name='角色')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='账户余额')
    phone = models.CharField(max_length=20, blank=True, verbose_name='手机号')
    avatar = models.CharField(max_length=255, blank=True, default='', verbose_name='头像')
    parent_agent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sub_members', verbose_name='上级代理'
    )
    api_key = models.CharField(max_length=64, blank=True, default='', verbose_name='API Key')
    api_secret = models.CharField(max_length=64, blank=True, default='', verbose_name='API Secret')
    referral_code = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name='推广码')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='注册时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'users'
        verbose_name = '用户'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def is_admin(self):
        return self.role == 'admin'

    def is_agent(self):
        return self.role == 'agent'

    def is_member(self):
        return self.role == 'member'

    def generate_api_keys(self):
        self.api_key = 'AK' + uuid.uuid4().hex[:30].upper()
        self.api_secret = 'SK' + secrets.token_hex(28)
        self.save(update_fields=['api_key', 'api_secret'])
        return self.api_key, self.api_secret
