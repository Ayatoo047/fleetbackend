from django.contrib import admin

from .models import Booking, CargoQuote, ContactMessage, JobApplication


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["reference", "first_name", "last_name", "date", "time", "pickup_city", "status", "created_at"]
    list_filter = ["status", "date"]
    search_fields = ["reference", "first_name", "last_name", "email", "phone", "pickup_city", "dropoff_city"]
    readonly_fields = ["reference", "created_at", "updated_at"]
    date_hierarchy = "date"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["email", "name", "topic", "status", "created_at"]
    list_filter = ["status", "topic"]
    search_fields = ["email", "name", "message"]
    readonly_fields = ["created_at"]


@admin.register(CargoQuote)
class CargoQuoteAdmin(admin.ModelAdmin):
    list_display = ["reference", "name", "direction", "goods_type", "weight_kg", "status", "created_at"]
    list_filter = ["status", "direction", "goods_type"]
    search_fields = ["reference", "name", "email", "whatsapp", "destination_city"]
    readonly_fields = ["reference", "created_at"]


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ["name", "role", "city", "work_status", "availability", "status", "created_at"]
    list_filter = ["status", "role", "work_status", "availability"]
    search_fields = ["name", "email", "phone", "city"]
    readonly_fields = ["created_at"]
