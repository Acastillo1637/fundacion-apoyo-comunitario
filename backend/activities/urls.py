from django.urls import path
from . import views

urlpatterns = [
    path('public-options/', views.public_options),
    path('requests/', views.submit_request),
    path('request-verification/', views.verify_request),
    path('public-events/', views.public_events),
    path('operations/options/', views.operator_options),
    path('operations/requests/', views.requests),
    path('operations/requests/<uuid:request_id>/', views.request_detail),
    path('operations/requests/<uuid:request_id>/transition/', views.request_transition),
    path('operations/requests/<uuid:request_id>/events/', views.event_create),
    path('operations/events/', views.events),
    path('operations/events/<uuid:event_id>/', views.event_detail),
    path('operations/events/<uuid:event_id>/transition/', views.event_transition),
]
