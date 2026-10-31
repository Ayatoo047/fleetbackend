from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view()),
    path("users", views.UserCollectionView.as_view()),
    path("users/<uuid:pk>", views.UserDetailView.as_view()),
]
