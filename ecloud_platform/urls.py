from django.contrib import admin
from django.urls import path, include
from apigateway.openai_compat import openai_models, openai_chat

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
]
