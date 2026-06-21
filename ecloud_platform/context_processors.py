from billing.models import SystemConfig


def platform_settings(request):
    return {
        'PLATFORM_NAME': SystemConfig.get('site_name', 'ECloud API平台'),
    }
