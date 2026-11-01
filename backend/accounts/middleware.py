from django.http import HttpResponseForbidden
from allauth.account.internal.flows.login import get_authentication_records


class AdminMfaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/') and request.user.is_authenticated:
            # allauth guarda el segundo factor en el registro de autenticación.
            methods = get_authentication_records(request, request.user)
            if not any(method.get('method') == 'mfa' for method in methods):
                return HttpResponseForbidden('Acceso administrativo: configura MFA en /accounts/2fa/ e inicia sesión en /accounts/login/.')
        return self.get_response(request)
