from django.urls import path

from . import views

urlpatterns = [
    path("services", views.ServiceCollectionView.as_view()),
    path("services/<uuid:pk>", views.ServiceDetailView.as_view()),
    path("fleet", views.FleetCollectionView.as_view()),
    path("fleet/<uuid:pk>", views.FleetDetailView.as_view()),
    path("articles", views.ArticleCollectionView.as_view()),
    path("articles/by-slug/<str:slug>", views.ArticleBySlugView.as_view()),
    path("articles/<uuid:pk>", views.ArticleDetailView.as_view()),
    path("day-trips", views.DayTripCollectionView.as_view()),
    path("day-trips/<uuid:pk>", views.DayTripDetailView.as_view()),
    path("faqs", views.FaqCollectionView.as_view()),
    path("faqs/<uuid:pk>", views.FaqDetailView.as_view()),
    path("settings", views.SettingsView.as_view()),
    path("uploads", views.UploadView.as_view()),
]
