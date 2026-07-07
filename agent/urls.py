from .views import agent_dashboard, member_list, promotion, admin_edit_user, withdrawal_apply, withdrawal_review, create_user
from django.urls import path

urlpatterns = [
    path('', agent_dashboard, name='agent_dashboard'),
    path('members/', member_list, name='agent_members'),
    path('promotion/', promotion, name='agent_promotion'),
    path('create-user/', create_user, name='create_user'),
    path('edit-user/<int:user_id>/', admin_edit_user, name='admin_edit_user'),
    path('withdrawal/', withdrawal_apply, name='withdrawal_apply'),
    path('withdrawal/review/', withdrawal_review, name='withdrawal_review'),
]
