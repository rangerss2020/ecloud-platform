from django.contrib import admin
from django.urls import path, include, re_path
from apigateway.openapi import open_api

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apimodels.urls')),
    path('users/', include('users.urls')),
    path('billing/', include('billing.urls')),
    path('agent/', include('agent.urls')),
    path('gateway/', include('apigateway.urls')),
    re_path(r'^api/v1/(?P<model_code>[a-zA-Z0-9_]+)/$', open_api, name='open_api'),
]
