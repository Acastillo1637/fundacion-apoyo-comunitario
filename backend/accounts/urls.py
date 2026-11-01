from django.urls import path
from . import views

urlpatterns = [
    path('session/', views.session_info),
    path('register/', views.register),
    path('login/', views.sign_in),
    path('logout/', views.sign_out),
    path('profile/', views.profile),
    path('operations/', views.operations),
]
