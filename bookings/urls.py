from django.urls import path

from . import views

urlpatterns = [
    path("bookings", views.BookingCollectionView.as_view()),
    path("bookings/stats", views.BookingStatsView.as_view()),
    path("bookings/<uuid:pk>", views.BookingDetailView.as_view()),
    path("contact-messages", views.ContactMessageCollectionView.as_view()),
    path("contact-messages/<uuid:pk>", views.ContactMessageDetailView.as_view()),
    path("cargo-quotes", views.CargoQuoteCollectionView.as_view()),
    path("cargo-quotes/<uuid:pk>", views.CargoQuoteDetailView.as_view()),
    path("job-applications", views.JobApplicationCollectionView.as_view()),
    path("job-applications/<uuid:pk>", views.JobApplicationDetailView.as_view()),
]
