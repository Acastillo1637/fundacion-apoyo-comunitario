from django.http import HttpResponseForbidden
from allauth.account.internal.flows.login import get_authentication_records
from django.contrib.auth import logout
from django.utils.cache import patch_cache_control, patch_vary_headers


class ApiCacheControlMiddleware:
    """Do not let browsers or shared proxies reuse API account responses."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/api/'):
            patch_cache_control(response, private=True, no_store=True, no_cache=True, must_revalidate=True, max_age=0)
            patch_vary_headers(response, ['Cookie'])
        return response


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
                return HttpResponseForbidden('Acceso administrativo: configura el segundo factor en Seguridad de cuenta e inicia sesión desde el portal de la fundación.')
        return self.get_response(request)
