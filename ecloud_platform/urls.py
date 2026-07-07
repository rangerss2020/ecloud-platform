from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apigateway.openai_compat import openai_models, openai_chat
from apigateway.video import video_generate, video_query

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apimodels.urls')),
    path('users/', include('users.urls')),
    path('billing/', include('billing.urls')),
    path('agent/', include('agent.urls')),
    path('gateway/', include('apigateway.urls')),
    path('v1/models', openai_models, name='openai_models'),
    path('v1/chat/completions', openai_chat, name='openai_chat'),
    path('chat/completions', openai_chat, name='chat_compat'),
    path('models', openai_models, name='models_compat'),
    path('v1/video/generations', video_generate, name='video_generate'),
    path('v1/video/generations/<str:task_id>', video_query, name='video_query'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
