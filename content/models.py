import uuid

from django.db import models


def localized():
    return {"pl": "", "en": ""}


class Service(models.Model):
    """A service on the website (menu, home page and Services page)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True, help_text="Anchor on the Services page, e.g. van-cargo.")
    title = models.JSONField(default=localized)
    summary = models.JSONField(default=localized)
    content = models.JSONField(default=localized, help_text="HTML from the admin rich-text editor.")
    image = models.CharField(max_length=500, blank=True)
    published = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "slug"]

    def __str__(self):
        return self.title.get("en") or self.slug


class FleetCar(models.Model):
    """A car offered for medium and long-term rental."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80)
    year = models.PositiveSmallIntegerField()
    price_per_week = models.PositiveIntegerField(help_text="PLN, including car service costs.")
    image = models.CharField(max_length=500, blank=True)
    color = models.CharField(max_length=7, default="#c8102e", help_text="Paint colour for the illustration.")
    fuel = models.JSONField(default=localized)
    summary = models.JSONField(default=localized)
    features = models.JSONField(default=dict, help_text='{"pl": [...], "en": [...]}')
    published = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return f"{self.name} ({self.year})"


class Article(models.Model):
    """A Knowledge Hub (News) article."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True)
    title = models.JSONField(default=localized)
    summary = models.JSONField(default=localized)
    body = models.JSONField(default=localized, help_text="HTML from the admin rich-text editor.")
    cover_image = models.CharField(max_length=500, blank=True)
    published = models.BooleanField(default=True)
    published_at = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title.get("en") or self.slug
