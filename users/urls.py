from django.urls import path
from .views import user_login, user_register, user_logout, user_profile, user_apikey, send_register_code

urlpatterns = [
    path('login/', user_login, name='user_login'),
    path('register/', user_register, name='user_register'),
    path('send-code/', send_register_code, name='send_register_code'),
    path('logout/', user_logout, name='user_logout'),
    path('profile/', user_profile, name='user_profile'),
    path('apikey/', user_apikey, name='user_apikey'),
]
