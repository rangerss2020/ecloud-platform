from .views import (
    dashboard, api_model_list, api_model_detail, api_docs
)
from django.urls import path

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('models/', api_model_list, name='api_model_list'),
    path('models/<int:model_id>/', api_model_detail, name='api_model_detail'),
    path('docs/', api_docs, name='api_docs'),
]
