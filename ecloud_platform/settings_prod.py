import os
from .settings import *

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', SECRET_KEY)

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.mysql'),
        'NAME': os.environ.get('DB_NAME', 'ecloud_platform'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}

STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
