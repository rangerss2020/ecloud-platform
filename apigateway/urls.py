from .views import gateway_index, api_test, api_records, chat, clear_chat, chat_stream, manage_channels, manage_models, manage_sensitive_words
from django.urls import path

urlpatterns = [
    path('', gateway_index, name='gateway_index'),
    path('test/<int:model_id>/', api_test, name='api_test'),
    path('records/', api_records, name='api_records'),
    path('chat/', chat, name='chat'),
    path('chat/stream/', chat_stream, name='chat_stream'),
    path('chat/clear/', clear_chat, name='clear_chat'),
    path('admin/channels/', manage_channels, name='manage_channels'),
    path('admin/models/', manage_models, name='manage_models'),
    path('admin/sensitive-words/', manage_sensitive_words, name='manage_sensitive_words'),
]
