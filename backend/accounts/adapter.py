from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from urllib.parse import urlsplit, urlunsplit


class FoundationAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        # Solo el endpoint controlado crea perfiles y recoge consentimientos.
        return False

    def portal_url(self, url):
        # Evita enviar al usuario al puerto del backend después de confirmar el correo.
        origin = urlsplit(settings.PUBLIC_APP_URL)
        if origin.scheme in ['http', 'https'] and origin.netloc and (settings.DEBUG or origin.scheme == 'https'):
            target = urlsplit(url)
            return urlunsplit((origin.scheme, origin.netloc, target.path, target.query, target.fragment))
        return url

    def get_reset_password_from_key_url(self, key):
        return self.portal_url(super().get_reset_password_from_key_url(key))

    def get_email_confirmation_url(self, request, emailconfirmation):
        return self.portal_url(super().get_email_confirmation_url(request, emailconfirmation))

    def set_password(self, user, password):
        # Un formulario de recuperación no debe sobrescribir un bloqueo administrativo concurrente.
        user.set_password(password)
        user.save(update_fields=['password'])
