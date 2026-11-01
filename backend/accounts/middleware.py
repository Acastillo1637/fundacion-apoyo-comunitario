from django.http import HttpResponseForbidden
from allauth.account.internal.flows.login import get_authentication_records
from django.contrib.auth import logout


class SessionVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.session.get('account_session_version', 0) != request.user.session_version:
            logout(request)
        return self.get_response(request)


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
