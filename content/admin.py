from django.contrib import admin

from .models import Article, FleetCar, Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["slug", "__str__", "published", "sort_order", "updated_at"]
    list_filter = ["published"]
    list_editable = ["published", "sort_order"]


@admin.register(FleetCar)
class FleetCarAdmin(admin.ModelAdmin):
    list_display = ["name", "year", "price_per_week", "published", "sort_order", "updated_at"]
    list_filter = ["published"]
    list_editable = ["published", "sort_order"]


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ["slug", "__str__", "published", "published_at", "updated_at"]
    list_filter = ["published"]
    date_hierarchy = "published_at"
