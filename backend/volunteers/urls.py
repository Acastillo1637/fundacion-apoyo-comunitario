from django.urls import path
from . import views

urlpatterns = [
    path('catalogs/', views.catalogs),
    path('qualifications/', views.qualifications),
    path('availability/', views.availability),
]
