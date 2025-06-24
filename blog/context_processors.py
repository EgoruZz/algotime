from django.conf import settings

def site_metadata(request):
    return {
        'SITE_NAME': 'AlgoTime',
        'SITE_DESCRIPTION': 'Изучаем алгоритмы вместе',
        'SITE_URL': settings.SITE_URL,
        'OG_IMAGE': f"{settings.STATIC_URL}blog/img/og-image.jpg",
    }
