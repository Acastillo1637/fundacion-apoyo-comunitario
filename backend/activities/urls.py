from django.urls import path
from . import views
from . import participation

urlpatterns = [
    path('participation-status/', participation.participation_status),
    path('participations/', participation.mine),
    path('participations/<uuid:participation_id>/decision/', participation.decision),
    path('notifications/', participation.notifications),
    path('operations/events/<uuid:event_id>/participants/', participation.event_participants),
    path('operations/events/<uuid:event_id>/positions/<int:position_id>/candidates/', participation.candidates),
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
