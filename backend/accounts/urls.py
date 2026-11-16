from django.urls import path
from . import views
from . import account_management
from . import requesters
from . import workspaces
from . import overview
from . import geography
from . import health
from . import privacy
from . import account_security
from activities import contacts, matching

urlpatterns = [
    path('security/', account_security.status),
    path('security/action/', account_security.action),
    path('privacy/requests/', privacy.requests),
    path('privacy/requests/<int:request_id>/review/', privacy.review),
    path('privacy/export/', privacy.export_own),
    path('health/live/', health.live),
    path('health/ready/', health.ready),
    path('volunteer/location/', geography.own_location),
    path('volunteer/contact-preferences/', contacts.preferences),
    path('maps/search/', geography.geocode),
    path('maps/config/', geography.map_config),
    path('management/matching-policy/', matching.configuration),
    path('operations/volunteers/<int:profile_id>/whatsapp/', contacts.profile_whatsapp),
    path('volunteer-overview/', overview.volunteer_overview),
    path('workspace-summary/', workspaces.summary),
    path('account-profile/', workspaces.account_profile),
    path('management/catalogs/<str:kind>/', workspaces.catalogs),
    path('operations/volunteers/', workspaces.volunteers),
    path('operations/volunteers/<int:profile_id>/', workspaces.volunteer_detail),
    path('requester/profile/', requesters.profile),
    path('requester/requests/', requesters.requests),
    path('requester/requests/<uuid:request_id>/', requesters.request_detail),
    path('session/', views.session_info),
    path('register/', views.register),
    path('login/', views.sign_in),
    path('logout/', views.sign_out),
    path('profile/', views.profile),
    path('operations/', views.operations),
    path('profile/onboarding/', views.onboarding),
    path('management/users/', account_management.accounts),
    path('management/users/<uuid:user_id>/', account_management.account_detail),
    path('management/users/<uuid:user_id>/access-email/', account_management.access_email),
]
