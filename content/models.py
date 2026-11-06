import uuid

from django.db import models


def localized():
    return {"pl": "", "en": ""}


BRANDS = ("service", "cargo")
FAQ_CATEGORIES = (
    "general",
    "onboarding",
    "rental",
    "payments",
    "platforms",
    "courier",
    "transfers",
    "agreements",
    "cargo",
    "support",
)


class Service(models.Model):
    """A service on the FleetFlow Service or FleetFlow Cargo page (`brand` decides which) and the home page."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.CharField(max_length=10, choices=[(b, b) for b in BRANDS], default="service")
    slug = models.SlugField(max_length=80, unique=True, help_text="Anchor on its page, e.g. air-cargo.")
    title = models.JSONField(default=localized)
    summary = models.JSONField(default=localized)
    content = models.JSONField(default=localized, help_text="HTML from the admin rich-text editor.")
    image = models.CharField(max_length=500, blank=True)
    published = models.BooleanField(default=True)
    coming_soon = models.BooleanField(default=False, help_text='Shown with a "Coming soon" label.')
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
    gallery = models.JSONField(default=list, blank=True, help_text="More photos of the car (up to 8 URLs).")
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
    """A post on the News page."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True, help_text="URL part shared by both languages.")
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


class Faq(models.Model):
    """A question on the FAQ page."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=20, choices=[(c, c) for c in FAQ_CATEGORIES], default="general")
    question = models.JSONField(default=localized)
    answer = models.JSONField(default=localized, help_text="HTML from the admin rich-text editor.")
    published = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0, help_text="Order within the category.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "created_at"]
        verbose_name = "FAQ entry"
        verbose_name_plural = "FAQ entries"

    def __str__(self):
        return self.question.get("en") or str(self.id)


def empty_address():
    return {"street": "", "city": "", "postalCode": ""}


def empty_credit():
    return {"author": "", "license": "", "source": ""}


class DayTrip(models.Model):
    """A destination in the booking page's "Day trips from Kraków" section."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True, help_text="Anchor on the booking page, e.g. wieliczka.")
    name = models.JSONField(default=localized)
    text = models.JSONField(default=localized)
    distance = models.JSONField(default=localized, help_text='e.g. {"pl": "ok. 15 km", "en": "about 15 km"}')
    duration = models.JSONField(default=localized, help_text="Suggested visit time.")
    photo = models.CharField(max_length=500, blank=True)
    photo_alt = models.JSONField(default=localized)
    photo_credit = models.JSONField(default=empty_credit, help_text='{"author", "license", "source"}; all may be "".')
    destination = models.JSONField(default=empty_address, help_text="Drop-off address the booking form is prefilled with.")
    published = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "slug"]

    def __str__(self):
        return self.name.get("en") or self.slug


BANNER_TONES = ("info", "warning")


class SiteSettings(models.Model):
    """Values FleetFlow changes in the admin without a code change. There is only one row."""

    cargo_rate_per_kg = models.DecimalField(
        max_digits=8, decimal_places=2, default=50, help_text="PLN per kg for the Cargo page's shipping estimator."
    )
    cargo_min_weight_kg = models.DecimalField(max_digits=7, decimal_places=2, default=1)
    cargo_estimator_enabled = models.BooleanField(default=True)
    rental_promo_enabled = models.BooleanField(default=True, help_text="Shows the first-week rental offer.")
    rental_first_week_discount_percent = models.PositiveSmallIntegerField(
        default=35, help_text="Discount on the first rental week only, 0–90."
    )
    # Contact details shown on the website and in customer emails. Empty values fall back to the
    # COMPANY_PHONE / CARGO_* environment settings (and the frontend's own defaults).
    contact_phone = models.CharField(max_length=40, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_whatsapp = models.CharField(max_length=40, blank=True, help_text="Empty: same as the phone number.")
    cargo_whatsapp = models.CharField(max_length=40, blank=True)
    cargo_email = models.EmailField(blank=True)
    # Site-wide announcement shown above the header on every public page.
    banner_enabled = models.BooleanField(default=False)
    banner_text = models.JSONField(default=localized)
    banner_tone = models.CharField(max_length=10, choices=[(t, t) for t in BANNER_TONES], default="info")

    class Meta:
        verbose_name = verbose_name_plural = "site settings"

    def __str__(self):
        return "Site settings"

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]
