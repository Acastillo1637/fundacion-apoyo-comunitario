from django.urls import path
from . import views
from . import account_management
from . import requesters

urlpatterns = [
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
