from django.urls import path
from . import views

urlpatterns = [
    path('', views.documents),
    path('review-queue/', views.review_queue),
    path('<uuid:document_id>/download/', views.download),
    path('<uuid:document_id>/review/', views.review),
]
