import secrets
import uuid

from django.db import models

from .constants import (
    AVAILABILITY,
    BOOKING_STATUSES,
    GOODS_TYPES,
    JOB_ROLES,
    LEAD_STATUSES,
    MESSAGE_STATUSES,
    SHIPPING_DIRECTIONS,
    WORK_STATUSES,
)

REFERENCE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def new_reference(prefix="FF"):
    return f"{prefix}-" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))


def choices(values):
    return [(value, value) for value in values]


ADDRESS_PARTS = ("street", "city", "state", "postal_code", "country")


class Booking(models.Model):
    """A ride booked on the website or entered by staff. Dates and times are Polish local time."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=12, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=[(s, s) for s in BOOKING_STATUSES], default="new", db_index=True)

    service_types = models.JSONField(default=list)
    specialized_transport = models.CharField(max_length=20, default="none")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_country_code = models.CharField(max_length=5)
    phone = models.CharField(max_length=20)
    email = models.EmailField(max_length=254)
    date = models.DateField(db_index=True)
    time = models.TimeField()

    pickup_street = models.CharField(max_length=200)
    pickup_city = models.CharField(max_length=100)
    pickup_state = models.CharField(max_length=100, blank=True)
    pickup_postal_code = models.CharField(max_length=20, blank=True)
    pickup_country = models.CharField(max_length=40, default="Poland")

    dropoff_street = models.CharField(max_length=200, blank=True)
    dropoff_city = models.CharField(max_length=100, blank=True)
    dropoff_state = models.CharField(max_length=100, blank=True)
    dropoff_postal_code = models.CharField(max_length=20, blank=True)
    dropoff_country = models.CharField(max_length=40, default="Poland")

    passengers = models.PositiveSmallIntegerField()
    luggage_kg = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    locale = models.CharField(max_length=2, default="pl")

    admin_notes = models.TextField(blank=True, help_text="Internal, never shown to customers.")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} – {self.first_name} {self.last_name}, {self.date} {self.time:%H:%M}"

    def address(self, prefix):
        return {part: getattr(self, f"{prefix}_{part}") for part in ADDRESS_PARTS}

    def set_address(self, prefix, address):
        for part in ADDRESS_PARTS:
            setattr(self, f"{prefix}_{part}", address[part])

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = new_reference()
            while Booking.objects.filter(reference=self.reference).exists():
                self.reference = new_reference()
        super().save(*args, **kwargs)


class ContactMessage(models.Model):
    """A message from the contact form (Contact, Rental and Jobs pages)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(max_length=254)
    phone = models.CharField(max_length=30, blank=True)
    topic = models.CharField(max_length=20, default="general")
    message = models.TextField()
    locale = models.CharField(max_length=2, default="pl")
    status = models.CharField(max_length=10, choices=[(s, s) for s in MESSAGE_STATUSES], default="new", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} ({self.topic})"


class CargoQuote(models.Model):
    """A shipping enquiry from the FleetFlow Cargo page (Nigeria ⇄ Poland)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=12, unique=True, editable=False)
    name = models.CharField(max_length=200)
    whatsapp = models.CharField(max_length=30)
    email = models.EmailField(max_length=254)
    direction = models.CharField(max_length=10, choices=choices(SHIPPING_DIRECTIONS))
    goods_type = models.CharField(max_length=20, choices=choices(GOODS_TYPES))
    description = models.TextField()
    weight_kg = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    destination_city = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    locale = models.CharField(max_length=2, default="pl")
    status = models.CharField(max_length=12, choices=choices(LEAD_STATUSES), default="new", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} – {self.name}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = new_reference("FC")
            while CargoQuote.objects.filter(reference=self.reference).exists():
                self.reference = new_reference("FC")
        super().save(*args, **kwargs)


class JobApplication(models.Model):
    """An application from the Careers page."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=10, choices=choices(JOB_ROLES))
    name = models.CharField(max_length=200)
    email = models.EmailField(max_length=254)
    phone = models.CharField(max_length=30)
    city = models.CharField(max_length=100)
    has_licence = models.BooleanField(help_text="Category B licence valid in Poland.")
    work_status = models.CharField(max_length=20, choices=choices(WORK_STATUSES))
    availability = models.CharField(max_length=20, choices=choices(AVAILABILITY))
    message = models.TextField(blank=True)
    locale = models.CharField(max_length=2, default="pl")
    status = models.CharField(max_length=12, choices=choices(LEAD_STATUSES), default="new", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.role})"
