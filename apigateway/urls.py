from .views import gateway_index, api_test, api_records, chat, clear_chat, chat_stream, manage_channels, manage_models, manage_sensitive_words, upload_media, admin_api_records
from .video import chat_video_poll
from django.urls import path

urlpatterns = [
    path('', gateway_index, name='gateway_index'),
    path('test/<int:model_id>/', api_test, name='api_test'),
    path('records/', api_records, name='api_records'),
    path('chat/', chat, name='chat'),
    path('chat/stream/', chat_stream, name='chat_stream'),
    path('chat/clear/', clear_chat, name='clear_chat'),
    path('chat/video/<str:task_id>/', chat_video_poll, name='chat_video_poll'),
    path('upload/', upload_media, name='upload_media'),
    path('admin/channels/', manage_channels, name='manage_channels'),
    path('admin/models/', manage_models, name='manage_models'),
    path('admin/sensitive-words/', manage_sensitive_words, name='manage_sensitive_words'),
    path('admin/api-records/', admin_api_records, name='admin_api_records'),
]
