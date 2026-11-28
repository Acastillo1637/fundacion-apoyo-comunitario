from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView

# Legacy bookmarks use the native account screen. Mutating these old forms
# is disabled so they cannot bypass the API's password + factor checks.
security_redirect = RedirectView.as_view(url='/seguridad', permanent=False, http_method_names=['get', 'head', 'options'])

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', RedirectView.as_view(url='/iniciar-sesion', permanent=False,
        http_method_names=['get', 'head', 'options'])),
    *[path('accounts/'+suffix, security_redirect) for suffix in [
        '2fa/', '2fa/totp/activate/', '2fa/totp/deactivate/',
        '2fa/recovery-codes/', '2fa/recovery-codes/generate/', '2fa/recovery-codes/download/',
        'email/', 'password/change/', 'password/set/',
    ]],
    path('accounts/', include('allauth.urls')),
    path('api/', include('accounts.urls')),
    path('api/volunteer/', include('volunteers.urls')),
    path('api/documents/', include('documents.urls')),
    path('api/activities/', include('activities.urls')),
]
