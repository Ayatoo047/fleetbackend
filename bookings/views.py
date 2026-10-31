from functools import partial

from django.db import transaction
from django.db.models import Count, Q, Value
from django.db.models.functions import Concat
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.throttling import BookingThrottle, ContactThrottle, EnquiryThrottle
from core.utils import flag, iso, now_in_poland, paginate

from . import emails
from .constants import BOOKING_STATUSES, LEAD_STATUSES, MESSAGE_STATUSES
from .models import Booking, CargoQuote, ContactMessage, JobApplication
from .validation import (
    validate_booking,
    validate_booking_admin_fields,
    validate_cargo_quote,
    validate_contact,
    validate_job_application,
    validate_lead_update,
    validate_message_update,
)


def _address_json(address):
    return {
        "street": address["street"],
        "city": address["city"],
        "state": address["state"],
        "postalCode": address["postal_code"],
        "country": address["country"],
    }


def booking_payload(b):
    """The `BookingPayload` fields of a booking."""
    return {
        "serviceTypes": b.service_types,
        "specializedTransport": b.specialized_transport,
        "firstName": b.first_name,
        "lastName": b.last_name,
        "phoneCountryCode": b.phone_country_code,
        "phone": b.phone,
        "email": b.email,
        "date": b.date.isoformat(),
        "time": b.time.strftime("%H:%M"),
        "pickup": _address_json(b.address("pickup")),
        "dropoff": _address_json(b.address("dropoff")),
        "passengers": b.passengers,
        "luggageKg": b.luggage_kg,
        "notes": b.notes,
        "locale": b.locale,
    }


def booking_to_json(b):
    return {
        "id": str(b.id),
        "reference": b.reference,
        **booking_payload(b),
        "status": b.status,
        "adminNotes": b.admin_notes,
        "createdAt": iso(b.created_at),
        "updatedAt": iso(b.updated_at),
    }


def apply_booking(booking, cleaned):
    for key, value in cleaned.items():
        if key in ("pickup", "dropoff"):
            booking.set_address(key, value)
        else:
            setattr(booking, key, value)


def get_booking(pk):
    booking = Booking.objects.filter(pk=pk).first()
    if booking is None:
        raise NotFound()
    return booking


class BookingCollectionView(APIView):
    """`POST` is the public booking form (and staff entering phone bookings); `GET` is the admin list."""

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "POST" else [IsAuthenticated()]

    def get_throttles(self):
        # BookingThrottle skips requests that carry a valid admin token.
        return [BookingThrottle()] if self.request.method == "POST" else []

    def get(self, request):
        qs = Booking.objects.all()
        status_filter = request.query_params.get("status")
        if status_filter in BOOKING_STATUSES:
            qs = qs.filter(status=status_filter)
        term = request.query_params.get("q", "").strip()
        if term:
            qs = qs.annotate(full_name=Concat("first_name", Value(" "), "last_name")).filter(
                Q(reference__icontains=term)
                | Q(full_name__icontains=term)
                | Q(email__icontains=term)
                | Q(phone__icontains=term)
                | Q(pickup_city__icontains=term)
                | Q(dropoff_city__icontains=term)
            )
        if flag(request, "upcoming"):
            qs = qs.filter(date__gte=now_in_poland().date()).order_by("date", "time", "created_at")
        else:
            qs = qs.order_by("-created_at")
        return Response(paginate(request, qs, booking_to_json))

    def post(self, request):
        is_staff = bool(request.user and request.user.is_authenticated)
        cleaned = validate_booking(request.data, allow_past=is_staff)
        booking = Booking()
        apply_booking(booking, cleaned)
        with transaction.atomic():
            booking.save()
            if not is_staff:
                transaction.on_commit(partial(emails.send_booking_emails, booking))
        return Response({"id": str(booking.id), "reference": booking.reference}, status=status.HTTP_201_CREATED)


class BookingStatsView(APIView):
    def get(self, request):
        counts = {s: 0 for s in BOOKING_STATUSES}
        for row in Booking.objects.values("status").annotate(n=Count("id")):
            counts[row["status"]] = row["n"]
        today = Booking.objects.filter(date=now_in_poland().date()).count()
        return Response({"counts": counts, "today": today})


class BookingDetailView(APIView):
    def get(self, request, pk):
        return Response(booking_to_json(get_booking(pk)))

    def patch(self, request, pk):
        booking = get_booking(pk)
        data = request.data if isinstance(request.data, dict) else {}
        payload_keys = set(booking_payload(booking)) & set(data)
        cleaned = {}
        if payload_keys:
            # Validate the booking as it will be after the update, so cross-field rules still hold.
            merged = {**booking_payload(booking), **{k: data[k] for k in payload_keys}}
            cleaned = validate_booking(merged, allow_past=True)
        cleaned.update(validate_booking_admin_fields(data))
        apply_booking(booking, cleaned)
        booking.save()
        return Response(booking_to_json(booking))

    def delete(self, request, pk):
        Booking.objects.filter(pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def message_to_json(m):
    return {
        "id": str(m.id),
        "name": m.name,
        "email": m.email,
        "phone": m.phone,
        "topic": m.topic,
        "message": m.message,
        "locale": m.locale,
        "status": m.status,
        "createdAt": iso(m.created_at),
    }


def get_message(pk):
    message = ContactMessage.objects.filter(pk=pk).first()
    if message is None:
        raise NotFound()
    return message


class ContactMessageCollectionView(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "POST" else [IsAuthenticated()]

    def get_throttles(self):
        return [ContactThrottle()] if self.request.method == "POST" else []

    def get(self, request):
        qs = ContactMessage.objects.order_by("-created_at")
        status_filter = request.query_params.get("status")
        if status_filter in MESSAGE_STATUSES:
            qs = qs.filter(status=status_filter)
        return Response(paginate(request, qs, message_to_json))

    def post(self, request):
        cleaned = validate_contact(request.data)
        with transaction.atomic():
            message = ContactMessage.objects.create(**cleaned)
            transaction.on_commit(partial(emails.send_contact_notification, message))
        return Response({"id": str(message.id)}, status=status.HTTP_201_CREATED)


class ContactMessageDetailView(APIView):
    def patch(self, request, pk):
        message = get_message(pk)
        message.status = validate_message_update(request.data)
        message.save(update_fields=["status"])
        return Response(message_to_json(message))

    def delete(self, request, pk):
        ContactMessage.objects.filter(pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def cargo_quote_to_json(q):
    return {
        "id": str(q.id),
        "reference": q.reference,
        "name": q.name,
        "whatsapp": q.whatsapp,
        "email": q.email,
        "direction": q.direction,
        "goodsType": q.goods_type,
        "description": q.description,
        "weightKg": None if q.weight_kg is None else float(q.weight_kg),
        "destinationCity": q.destination_city,
        "notes": q.notes,
        "locale": q.locale,
        "status": q.status,
        "createdAt": iso(q.created_at),
    }


def job_application_to_json(a):
    return {
        "id": str(a.id),
        "role": a.role,
        "name": a.name,
        "email": a.email,
        "phone": a.phone,
        "city": a.city,
        "hasLicence": a.has_licence,
        "workStatus": a.work_status,
        "availability": a.availability,
        "message": a.message,
        "locale": a.locale,
        "status": a.status,
        "createdAt": iso(a.created_at),
    }


class LeadCollectionView(APIView):
    """
    Public `POST` of an enquiry, and the staff list (`?status=&page=&pageSize=`, newest first).
    The website emails the team about new enquiries, so the API sends no email for them.
    """

    model = None
    to_json = None
    validate = None

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "POST" else [IsAuthenticated()]

    def get_throttles(self):
        return [EnquiryThrottle()] if self.request.method == "POST" else []

    def get(self, request):
        qs = self.model.objects.order_by("-created_at")
        status_filter = request.query_params.get("status")
        if status_filter in LEAD_STATUSES:
            qs = qs.filter(status=status_filter)
        return Response(paginate(request, qs, type(self).to_json))

    def post(self, request):
        lead = self.model.objects.create(**type(self).validate(request.data))
        return Response(self.created_body(lead), status=status.HTTP_201_CREATED)

    def created_body(self, lead):
        return {"id": str(lead.id)}


class LeadDetailView(APIView):
    """Staff `PATCH` (`{ status }`) and `DELETE`."""

    model = None
    to_json = None

    def patch(self, request, pk):
        lead = self.model.objects.filter(pk=pk).first()
        if lead is None:
            raise NotFound()
        lead.status = validate_lead_update(request.data)
        lead.save(update_fields=["status"])
        return Response(type(self).to_json(lead))

    def delete(self, request, pk):
        self.model.objects.filter(pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CargoQuoteCollectionView(LeadCollectionView):
    model, to_json, validate = CargoQuote, cargo_quote_to_json, validate_cargo_quote

    def created_body(self, lead):
        return {"id": str(lead.id), "reference": lead.reference}


class CargoQuoteDetailView(LeadDetailView):
    model, to_json = CargoQuote, cargo_quote_to_json


class JobApplicationCollectionView(LeadCollectionView):
    model, to_json, validate = JobApplication, job_application_to_json, validate_job_application


class JobApplicationDetailView(LeadDetailView):
    model, to_json = JobApplication, job_application_to_json
