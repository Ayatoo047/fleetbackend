"""
Every email the website sends: team notifications for bookings, contact messages, cargo quote
requests and job applications, and customer confirmations.

Sending happens after the database commit. A failure is logged without failing the request:
the enquiry is already saved and staff can see it in the admin panel.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)

# English labels for team emails (as in the frontend's dictionaries and src/lib/admin/labels.ts).
SERVICE_LABELS = {"city": "City ride", "long_distance": "Long-distance ride", "hourly": "Hourly ride / driver at disposal"}
TRANSPORT_LABELS = {
    "airport": "Airport transfer",
    "van": "Van / cargo",
    "wheelchair": "Wheelchair",
    "child_seat": "Child seat",
    "pet": "Pet",
    "executive": "Executive",
}
TOPIC_LABELS = {
    "general": "General question",
    "booking": "Taxi booking",
    "rental": "Car rental",
    "driver": "Working as a driver",
    "partner": "Fleet partnership (car owners & investors)",
    "business": "Business / fleet services",
    "cargo": "Cargo & logistics",
}
DIRECTION_LABELS = {"ng_pl": "Nigeria → Poland", "pl_ng": "Poland → Nigeria"}
GOODS_LABELS = {"food": "Food items", "personal": "Personal effects", "documents": "Documents", "other": "Other"}
ROLE_LABELS = {"taxi": "Taxi driver", "courier": "Courier & delivery partner (interest)"}
WORK_STATUS_LABELS = {
    "eu": "EU citizen",
    "permit": "Residence or work permit",
    "student": "Student status",
    "needs_permit": "Needs a work permit",
}
AVAILABILITY_LABELS = {"full_time": "Full-time", "part_time": "Part-time", "weekends": "Weekends"}

BOOKING_CONFIRMATION = {
    "pl": {
        "subject": "Otrzymaliśmy Twoją rezerwację {reference} – FleetFlow Service",
        "body": (
            "Dzień dobry {first_name},\n\n"
            "dziękujemy za rezerwację w FleetFlow Service. Skontaktujemy się z Tobą wkrótce, aby potwierdzić przejazd.\n\n"
            "Numer rezerwacji: {reference}\n"
            "Usługa: {services}\n"
            "Data i godzina: {date} {time}\n"
            "Odbiór: {pickup}\n"
            "Cel: {dropoff}\n"
            "Pasażerowie: {passengers}\n\n"
            "Jeśli chcesz coś zmienić, odpowiedz na tę wiadomość lub zadzwoń pod numer {phone}.\n\n"
            "Pozdrawiamy,\nZespół FleetFlow Service\n"
        ),
        "services": {"city": "Przejazd miejski", "long_distance": "Przejazd międzymiastowy", "hourly": "Przejazd godzinowy"},
    },
    "en": {
        "subject": "We have received your booking {reference} – FleetFlow Service",
        "body": (
            "Hello {first_name},\n\n"
            "thank you for booking with FleetFlow Service. We will contact you shortly to confirm your ride.\n\n"
            "Booking reference: {reference}\n"
            "Service: {services}\n"
            "Date and time: {date} {time}\n"
            "Pickup: {pickup}\n"
            "Drop-off: {dropoff}\n"
            "Passengers: {passengers}\n\n"
            "If anything needs to change, reply to this email or call us on {phone}.\n\n"
            "Kind regards,\nThe FleetFlow Service team\n"
        ),
        "services": {"city": "City ride", "long_distance": "Long-distance ride", "hourly": "Hourly ride"},
    },
}

CARGO_CONFIRMATION = {
    "pl": {
        "subject": "FleetFlow Cargo – otrzymaliśmy Twoje zapytanie ({reference})",
        "body": (
            "Dzień dobry {name},\n\n"
            "dziękujemy za zapytanie o wysyłkę. Numer zapytania: {reference}.\n\n"
            "Sprawdzimy szczegóły i odpowiemy e-mailem lub na WhatsAppie z potwierdzeniem, ceną i informacją o odbiorze. "
            "Cło i VAT importowy nie są wliczone w cenę wysyłki.\n\n"
            "FleetFlow Cargo\nWhatsApp: {whatsapp}\nE-mail: {email}\n"
        ),
    },
    "en": {
        "subject": "FleetFlow Cargo – we have your request ({reference})",
        "body": (
            "Hello {name},\n\n"
            "thank you for your shipping enquiry. Your reference is {reference}.\n\n"
            "We will review the details and reply by email or WhatsApp to confirm acceptance, pricing and collection "
            "arrangements. Customs duties and import VAT are not included in the shipping price.\n\n"
            "FleetFlow Cargo\nWhatsApp: {whatsapp}\nE-mail: {email}\n"
        ),
    },
}


def lines(rows):
    """"Label: value" lines, skipping empty values."""
    return "\n".join(f"{label}: {value}" for label, value in rows if value not in ("", None))


def _address(a):
    return ", ".join(p for p in (a["street"], a["postal_code"], a["city"]) if p)


def _admin_link(path):
    return f"{settings.SITE_URL}/admin/{path}"


def _send(subject, body, to, reply_to=None):
    if not to:
        return
    subject = " ".join(subject.split())  # header-safe: no line breaks from user input
    try:
        EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, to, reply_to=reply_to).send()
    except Exception:
        logger.exception("Could not send email %r to %s", subject, to)


def _team(subject, body, reply_to):
    _send(subject, body, settings.TEAM_EMAILS, reply_to=[reply_to])


def send_booking_emails(booking):
    date, time = booking.date.isoformat(), booking.time.strftime("%H:%M")
    pickup, dropoff = booking.address("pickup"), booking.address("dropoff")
    route = " → ".join(c for c in (pickup["city"], dropoff["city"]) if c)
    _team(
        f"New taxi booking {booking.reference} – {date} {time} – {route}",
        lines(
            [
                ("Reference", booking.reference),
                ("Service", ", ".join(SERVICE_LABELS.get(s, s) for s in booking.service_types)),
                ("Transport", TRANSPORT_LABELS.get(booking.specialized_transport)),
                ("Pickup", f"{date} {time}"),
                ("From", _address(pickup)),
                ("To", _address(dropoff)),
                ("Passengers", booking.passengers),
                ("Luggage", None if booking.luggage_kg is None else f"{booking.luggage_kg} kg"),
                ("Customer", f"{booking.first_name} {booking.last_name}"),
                ("Phone", f"{booking.phone_country_code} {booking.phone}"),
                ("Email", booking.email),
                ("Notes", booking.notes),
            ]
        )
        + f"\n\nOpen the booking: {_admin_link(f'bookings/{booking.id}')}",
        booking.email,
    )

    if settings.SEND_BOOKING_CONFIRMATION:
        text = BOOKING_CONFIRMATION[booking.locale if booking.locale in BOOKING_CONFIRMATION else "pl"]
        values = {
            "reference": booking.reference,
            "first_name": booking.first_name,
            "services": ", ".join(text["services"].get(s, s) for s in booking.service_types),
            "date": date,
            "time": time,
            "pickup": _address(pickup) or "–",
            "dropoff": _address(dropoff) or "–",
            "passengers": booking.passengers,
            "phone": settings.COMPANY_PHONE,
        }
        reply_to = [settings.COMPANY_REPLY_TO] if settings.COMPANY_REPLY_TO else None
        _send(text["subject"].format(**values), text["body"].format(**values), [booking.email], reply_to=reply_to)


def send_contact_notification(message):
    topic = TOPIC_LABELS.get(message.topic, message.topic)
    _team(
        f"Website message – {topic}" + (f" – {message.name}" if message.name else ""),
        lines([("Topic", topic), ("Name", message.name), ("Email", message.email), ("Phone", message.phone)])
        + f"\n\n{message.message}\n\nOpen the admin: {_admin_link('messages')}",
        message.email,
    )


def send_cargo_quote_emails(quote):
    direction = DIRECTION_LABELS.get(quote.direction, quote.direction)
    _team(
        f"Cargo quote request {quote.reference} – {direction}",
        lines(
            [
                ("Reference", quote.reference),
                ("Direction", direction),
                ("Type of goods", GOODS_LABELS.get(quote.goods_type, quote.goods_type)),
                ("Description", quote.description),
                ("Estimated weight", None if quote.weight_kg is None else f"{quote.weight_kg.normalize():f} kg"),
                ("Destination city in Poland", quote.destination_city),
                ("Additional information", quote.notes),
                ("Name", quote.name),
                ("WhatsApp", quote.whatsapp),
                ("Email", quote.email),
                ("Language", "Polish" if quote.locale == "pl" else "English"),
            ]
        )
        + f"\n\nReply to this email to answer the customer, or open the admin: {_admin_link('cargo-quotes')}",
        quote.email,
    )

    text = CARGO_CONFIRMATION[quote.locale if quote.locale in CARGO_CONFIRMATION else "pl"]
    values = {"name": quote.name, "reference": quote.reference, "whatsapp": settings.CARGO_WHATSAPP, "email": settings.CARGO_EMAIL}
    _send(text["subject"].format(**values), text["body"].format(**values), [quote.email], reply_to=[settings.CARGO_EMAIL])


def send_job_application_notification(application):
    role = ROLE_LABELS.get(application.role, application.role)
    _team(
        f"New application – {role} – {application.name}",
        lines(
            [
                ("Role", role),
                ("Name", application.name),
                ("Phone", application.phone),
                ("Email", application.email),
                ("City", application.city),
                ("Category B licence", "Yes" if application.has_licence else "No"),
                ("Right to work", WORK_STATUS_LABELS.get(application.work_status, application.work_status)),
                ("Availability", AVAILABILITY_LABELS.get(application.availability, application.availability)),
                ("Message", application.message),
            ]
        )
        + f"\n\nOpen the admin: {_admin_link('applications')}",
        application.email,
    )
