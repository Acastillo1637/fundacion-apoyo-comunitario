from django.conf import settings


def account_environment(request):
    return {
        'foundation_name': settings.FOUNDATION_NAME,
        'console_email_mode': settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend',
    }
