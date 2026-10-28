from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "name", "role", "is_active", "last_login"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "name"]
    readonly_fields = ["created_at", "last_login"]
    fieldsets = [
        (None, {"fields": ["email", "name", "role", "password"]}),
        ("Access", {"fields": ["is_active", "is_staff", "is_superuser"]}),
        ("Dates", {"fields": ["created_at", "last_login"]}),
    ]
    add_fieldsets = [(None, {"classes": ["wide"], "fields": ["email", "name", "role", "password1", "password2"]})]
