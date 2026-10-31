from django.urls import path

from . import views

urlpatterns = [
    path("services", views.ServiceCollectionView.as_view()),
    path("services/<uuid:pk>", views.ServiceDetailView.as_view()),
    path("fleet", views.FleetCollectionView.as_view()),
    path("fleet/<uuid:pk>", views.FleetDetailView.as_view()),
    path("faqs", views.FaqCollectionView.as_view()),
    path("faqs/<uuid:pk>", views.FaqDetailView.as_view()),
    path("settings", views.SettingsView.as_view()),
    path("uploads", views.UploadView.as_view()),
]
