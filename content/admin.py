from django.contrib import admin

from .models import Faq, FleetCar, Service, SiteSettings


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["slug", "__str__", "brand", "published", "coming_soon", "sort_order", "updated_at"]
    list_filter = ["brand", "published", "coming_soon"]
    list_editable = ["published", "coming_soon", "sort_order"]


@admin.register(FleetCar)
class FleetCarAdmin(admin.ModelAdmin):
    list_display = ["name", "year", "price_per_week", "published", "sort_order", "updated_at"]
    list_filter = ["published"]
    list_editable = ["published", "sort_order"]


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ["__str__", "category", "published", "sort_order", "updated_at"]
    list_filter = ["category", "published"]
    list_editable = ["published", "sort_order"]


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ["__str__", "cargo_rate_per_kg", "cargo_min_weight_kg", "cargo_estimator_enabled"]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
