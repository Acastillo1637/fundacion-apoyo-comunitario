from pathlib import Path
from urllib.parse import urlsplit
from django.conf import settings
from django.core.checks import Error, Warning, Tags, register


@register(Tags.security, deploy=True)
def production_readiness(app_configs, **kwargs):
    if settings.DEBUG:
        return []
    issues=[]
    public=urlsplit(settings.PUBLIC_APP_URL)
    if public.scheme!='https' or not public.hostname or public.hostname not in settings.ALLOWED_HOSTS or '*' in settings.ALLOWED_HOSTS:
        issues.append(Error('Configura PUBLIC_APP_URL HTTPS y un ALLOWED_HOSTS explícito coincidente.',id='pro12.E001'))
    if not settings.DATA_RETENTION_NOTICE.strip():
        issues.append(Error('La fundación debe aprobar y configurar DATA_RETENTION_NOTICE antes de publicar.',id='pro12.E002'))
    if not settings.EMAIL_HOST or 'console' in settings.EMAIL_BACKEND:
        issues.append(Error('Configura el servicio de correo real antes de habilitar registro y recuperación públicos.',id='pro12.E003'))
    if not settings.CLAMAV_HOST:
        issues.append(Error('Configura el análisis antimalware; las cargas de producción fallan de forma cerrada sin él.',id='pro12.E004'))
    options=settings.DATABASES['default'].get('OPTIONS',{})
    if options.get('sslmode')!='verify-full':
        issues.append(Warning('En producción verifica identidad del servidor PostgreSQL con sslmode=verify-full y su CA.',id='pro12.W001'))
    private=Path(settings.PRIVATE_DOCUMENT_ROOT).resolve()
    roots=[Path(settings.STATIC_ROOT).resolve(),(settings.BASE_DIR.parent/'frontend'/'dist').resolve()]
    if any(private==root or private.is_relative_to(root) for root in roots):
        issues.append(Error('PRIVATE_DOCUMENT_ROOT no puede estar dentro de un directorio público.',id='pro12.E005'))
    return issues
