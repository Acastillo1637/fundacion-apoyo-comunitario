from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('api/', include('accounts.urls')),
    path('api/volunteer/', include('volunteers.urls')),
]
