from pathlib import Path
from email.utils import parseaddr
from urllib.parse import urlsplit
from django.conf import settings
from django.core.checks import Error, Warning, Tags, register
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


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
    try:
        sender = parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
        validate_email(sender)
        if '\r' in settings.DEFAULT_FROM_EMAIL or '\n' in settings.DEFAULT_FROM_EMAIL or sender.rsplit('@', 1)[-1] in ['localhost', 'example.org', 'example.com']:
            raise ValidationError('Remitente de ejemplo.')
    except ValidationError:
        issues.append(Error('Configura DEFAULT_FROM_EMAIL con un remitente institucional autorizado.',id='pro12.E006'))
    if not (settings.EMAIL_USE_TLS or settings.EMAIL_USE_SSL) or (settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL):
        issues.append(Error('Activa exclusivamente STARTTLS o TLS implícito para el correo.',id='pro12.E007'))
    if bool(settings.EMAIL_HOST_USER) != bool(settings.EMAIL_HOST_PASSWORD):
        issues.append(Error('Completa ambos datos de autenticación SMTP o usa un relay autorizado sin autenticación.',id='pro12.E010'))
    if public.username or public.password or public.query or public.fragment or public.path not in ['', '/']:
        issues.append(Error('PUBLIC_APP_URL debe ser un origen HTTPS sin credenciales, ruta, consulta ni fragmento.',id='pro12.E008'))
    if not settings.CLAMAV_HOST:
        issues.append(Error('Configura el análisis antimalware; las cargas de producción fallan de forma cerrada sin él.',id='pro12.E004'))
    options=settings.DATABASES['default'].get('OPTIONS',{})
    if options.get('sslmode') not in ['require', 'verify-ca', 'verify-full']:
        issues.append(Error('La conexión PostgreSQL de producción debe exigir TLS.',id='pro12.E011'))
    if options.get('sslmode')!='verify-full':
        issues.append(Warning('En producción verifica identidad del servidor PostgreSQL con sslmode=verify-full y su CA.',id='pro12.W001'))
    private=Path(settings.PRIVATE_DOCUMENT_ROOT).resolve()
    roots=[Path(settings.STATIC_ROOT).resolve(),(settings.BASE_DIR.parent/'frontend'/'dist').resolve()]
    if any(private==root or private.is_relative_to(root) for root in roots):
        issues.append(Error('PRIVATE_DOCUMENT_ROOT no puede estar dentro de un directorio público.',id='pro12.E005'))
    if not Path(settings.PRIVATE_DOCUMENT_ROOT).is_absolute():
        issues.append(Error('Configura PRIVATE_DOCUMENT_ROOT como ruta absoluta privada y persistente.',id='pro12.E009'))
    return issues
