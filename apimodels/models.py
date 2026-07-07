from django.db import models
from django.utils import timezone


class SiteConfig(models.Model):
    key = models.CharField(max_length=50, unique=True, verbose_name='配置键')
    value = models.TextField(blank=True, verbose_name='配置值')
    description = models.CharField(max_length=200, blank=True, verbose_name='说明')

    class Meta:
        db_table = 'site_config'
        verbose_name = '站点配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.key

    @classmethod
    def get(cls, key, default=''):
        obj = cls.objects.filter(key=key).first()
        return obj.value if obj else default


class Capability(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name='能力编码')
    name = models.CharField(max_length=50, verbose_name='能力名称')
    icon = models.CharField(max_length=10, default='', verbose_name='图标')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'capabilities'
        verbose_name = '模型能力'
        verbose_name_plural = verbose_name
        ordering = ['sort_order']

    def __str__(self):
        return self.name


class Channel(models.Model):
    STATUS_CHOICES = (
        ('enabled', '启用'),
        ('disabled', '禁用'),
    )
    AUTH_TYPES = (
        ('hmac', 'AK/SK签名'),
        ('bearer', 'Bearer Token'),
    )

    name = models.CharField(max_length=100, unique=True, verbose_name='渠道名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='渠道编码')
    description = models.TextField(blank=True, verbose_name='描述')
    base_url = models.CharField(max_length=255, verbose_name='基础URL')
    auth_type = models.CharField(max_length=10, choices=AUTH_TYPES, default='hmac', verbose_name='认证方式')
    access_key = models.CharField(max_length=128, blank=True, default='', verbose_name='AccessKey')
    secret_key = models.CharField(max_length=128, blank=True, default='', verbose_name='SecretKey')
    api_key = models.CharField(max_length=256, blank=True, default='', verbose_name='API Key (Bearer)')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='enabled', verbose_name='状态')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'channels'
        verbose_name = '渠道'
        verbose_name_plural = verbose_name
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.name}({self.code})"


class ApiModel(models.Model):
    METHOD_CHOICES = (
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
    )
    STATUS_CHOICES = (
        ('enabled', '启用'),
        ('disabled', '禁用'),
    )
    BILL_TYPE_CHOICES = (
        ('per_call', '按次计费'),
        ('per_unit', '按量计费'),
        ('free', '免费'),
    )
    UNIT_CHOICES = (
        ('', '不适用'),
        ('per_1k', '千tokens (K)'),
        ('per_1m', '百万tokens (M)'),
    )
    TASK_TYPE_CHOICES = (
        ('chat', '对话'),
        ('video', '视频生成'),
    )

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='api_models', verbose_name='所属渠道')
    name = models.CharField(max_length=100, verbose_name='模型名称')
    code = models.CharField(max_length=50, verbose_name='模型编码')
    icon = models.CharField(max_length=255, blank=True, default='', verbose_name='图标')
    description = models.TextField(blank=True, verbose_name='描述')
    servlet_path = models.CharField(max_length=255, verbose_name='接口路径')
    http_method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='POST', verbose_name='请求方法')
    task_type = models.CharField(max_length=10, choices=TASK_TYPE_CHOICES, default='chat', verbose_name='任务类型')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='enabled', verbose_name='状态')
    bill_type = models.CharField(max_length=10, choices=BILL_TYPE_CHOICES, default='per_call', verbose_name='计费方式')
    price = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='单价(元)')
    unit_type = models.CharField(max_length=10, choices=UNIT_CHOICES, default='', blank=True, verbose_name='计量单位')
    capabilities = models.ManyToManyField(Capability, blank=True, verbose_name='模型能力')
    resolution_options = models.JSONField(default=list, blank=True, verbose_name='分辨率定价')
    duration_options = models.JSONField(default=list, blank=True, verbose_name='时长定价')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'api_models'
        verbose_name = 'API模型'
        verbose_name_plural = verbose_name
        unique_together = [('channel', 'code')]
        ordering = ['channel', 'sort_order']

    def __str__(self):
        return f"[{self.channel.code}] {self.name}"


class ApiParameter(models.Model):
    PARAM_TYPE_CHOICES = (
        ('string', '字符串'),
        ('integer', '整数'),
        ('number', '数字'),
        ('boolean', '布尔'),
        ('array', '数组'),
        ('object', '对象'),
    )

    model = models.ForeignKey(ApiModel, on_delete=models.CASCADE, related_name='parameters', verbose_name='所属模型')
    param_name = models.CharField(max_length=100, verbose_name='参数名')
    param_type = models.CharField(max_length=10, choices=PARAM_TYPE_CHOICES, default='string', verbose_name='参数类型')
    required = models.BooleanField(default=False, verbose_name='是否必填')
    default_value = models.CharField(max_length=500, blank=True, verbose_name='默认值')
    description = models.CharField(max_length=255, blank=True, verbose_name='参数说明')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'api_parameters'
        verbose_name = 'API参数'
        verbose_name_plural = verbose_name
        ordering = ['sort_order']


class ApiUsageLog(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, verbose_name='用户')
    model = models.ForeignKey(ApiModel, on_delete=models.SET_NULL, null=True, verbose_name='API模型')
    channel = models.ForeignKey(Channel, on_delete=models.SET_NULL, null=True, verbose_name='渠道')
    request_params = models.JSONField(default=dict, verbose_name='请求参数')
    response_data = models.JSONField(default=dict, verbose_name='响应数据')
    response_state = models.CharField(max_length=20, blank=True, verbose_name='响应状态')
    cost = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='费用')
    ip_address = models.CharField(max_length=50, blank=True, verbose_name='IP地址')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='调用时间')

    class Meta:
        db_table = 'api_usage_logs'
        verbose_name = 'API调用日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
