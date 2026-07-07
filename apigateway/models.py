from django.db import models
from django.conf import settings
from django.utils import timezone


class SensitiveWord(models.Model):
    LEVEL_CHOICES = (
        ('block', '拦截'),
        ('replace', '替换'),
        ('audit', '审核'),
    )

    word = models.CharField(max_length=100, unique=True, verbose_name='敏感词')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='replace', verbose_name='处理级别')
    replacement = models.CharField(max_length=50, default='***', verbose_name='替换文本')
    category = models.CharField(max_length=50, blank=True, verbose_name='分类')
    enabled = models.BooleanField(default=True, verbose_name='启用')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='添加时间')

    class Meta:
        db_table = 'sensitive_words'
        verbose_name = '敏感词'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.word} ({self.get_level_display()})"


class VideoTask(models.Model):
    STATUS_CHOICES = (
        ('pending', '排队中'),
        ('running', '生成中'),
        ('succeeded', '已完成'),
        ('failed', '失败'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='用户')
    api_model = models.ForeignKey('apimodels.ApiModel', on_delete=models.SET_NULL, null=True, verbose_name='模型')
    remote_task_id = models.CharField(max_length=128, verbose_name='远端任务ID')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    prompt_text = models.TextField(blank=True, verbose_name='提示词')
    request_data = models.JSONField(default=dict, verbose_name='请求参数')
    video_url = models.CharField(max_length=500, blank=True, verbose_name='视频URL')
    local_path = models.CharField(max_length=500, blank=True, verbose_name='本地路径')
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='费用')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'video_tasks'
        verbose_name = '视频生成任务'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.remote_task_id}"


class ApiRequestRecord(models.Model):
    STATUS_CHOICES = (
        ('success', '成功'),
        ('failed', '失败'),
        ('pending', '处理中'),
        ('blocked', '已拦截'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='调用用户')
    api_model = models.ForeignKey(
        'apimodels.ApiModel', on_delete=models.SET_NULL, null=True, verbose_name='API模型'
    )
    request_method = models.CharField(max_length=10, verbose_name='请求方法')
    request_url = models.CharField(max_length=500, verbose_name='请求URL')
    request_params = models.JSONField(default=dict, verbose_name='请求参数')
    response_data = models.JSONField(default=dict, verbose_name='响应数据')
    response_state = models.CharField(max_length=20, verbose_name='响应状态')
    cost = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='本次费用')
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='调用前余额')
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='调用后余额')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    filter_hits = models.TextField(blank=True, verbose_name='敏感词命中')
    duration_ms = models.IntegerField(default=0, verbose_name='耗时(毫秒)')
    prompt_tokens = models.IntegerField(default=0, verbose_name='提示Token')
    completion_tokens = models.IntegerField(default=0, verbose_name='生成Token')
    ip_address = models.CharField(max_length=50, blank=True, verbose_name='IP地址')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='调用时间')

    class Meta:
        db_table = 'api_request_records'
        verbose_name = 'API请求记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

