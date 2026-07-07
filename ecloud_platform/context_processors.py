from django.conf import settings
from apimodels.models import SiteConfig


def platform_settings(request):
    return {
        'PLATFORM_NAME': SiteConfig.get('site_name', 'Seedance AI 平台'),
        'ICP': SiteConfig.get('icp', ''),
        'FOOTER_TEXT': SiteConfig.get('footer_text', ''),
    }
