"""
Booking and contact-form emails. Sending happens after the database commit, and a failure
is logged without failing the request: the booking is already saved and staff can see it.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)

SERVICE_LABELS = {
    "pl": {"city": "Przejazd miejski", "long_distance": "Przejazd międzymiastowy", "hourly": "Przejazd godzinowy"},
    "en": {"city": "City ride", "long_distance": "Long-distance ride", "hourly": "Hourly ride"},
}

CUSTOMER_TEXT = {
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
    },
}


def _address(booking, prefix):
    a = booking.address(prefix)
    parts = [a["street"], " ".join(p for p in (a["postal_code"], a["city"]) if p), a["state"], a["country"]]
    return ", ".join(p for p in parts if p) if a["city"] else "–"


def _send(subject, body, to, reply_to=None):
    if not to:
        return
    subject = " ".join(subject.split())  # header-safe: no line breaks from user input
    try:
        EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, to, reply_to=reply_to).send()
    except Exception:
        logger.exception("Could not send email %r to %s", subject, to)


def send_booking_emails(booking):
    """Staff notification plus the customer's confirmation, in the language they booked in."""
    locale = booking.locale if booking.locale in CUSTOMER_TEXT else "pl"
    labels = SERVICE_LABELS[locale]
    values = {
        "reference": booking.reference,
        "first_name": booking.first_name,
        "services": ", ".join(labels.get(s, s) for s in booking.service_types),
        "date": booking.date.isoformat(),
        "time": booking.time.strftime("%H:%M"),
        "pickup": _address(booking, "pickup"),
        "dropoff": _address(booking, "dropoff"),
        "passengers": booking.passengers,
        "phone": settings.COMPANY_PHONE,
    }

    staff_body = (
        f"New booking {booking.reference}\n\n"
        f"Customer: {booking.first_name} {booking.last_name}\n"
        f"Phone: {booking.phone_country_code} {booking.phone}\n"
        f"Email: {booking.email}\n"
        f"Service: {', '.join(SERVICE_LABELS['en'].get(s, s) for s in booking.service_types)}\n"
        f"Specialised transport: {booking.specialized_transport}\n"
        f"Date and time: {values['date']} {values['time']} (Polish time)\n"
        f"Pickup: {_address(booking, 'pickup')}\n"
        f"Drop-off: {_address(booking, 'dropoff')}\n"
        f"Passengers: {booking.passengers}\n"
        f"Luggage: {'–' if booking.luggage_kg is None else f'{booking.luggage_kg} kg'}\n"
        f"Language: {booking.locale}\n\n"
        f"Notes:\n{booking.notes or '–'}\n"
    )
    _send(f"New booking {booking.reference} – {values['date']} {values['time']}", staff_body,
          settings.STAFF_NOTIFICATION_EMAILS, reply_to=[booking.email])

    if settings.SEND_CUSTOMER_CONFIRMATION:
        text = CUSTOMER_TEXT[locale]
        reply_to = [settings.COMPANY_REPLY_TO] if settings.COMPANY_REPLY_TO else None
        _send(text["subject"].format(**values), text["body"].format(**values), [booking.email], reply_to=reply_to)


def send_contact_notification(message):
    body = (
        f"New message from the website contact form\n\n"
        f"Topic: {message.topic}\n"
        f"Name: {message.name or '–'}\n"
        f"Email: {message.email}\n"
        f"Phone: {message.phone or '–'}\n"
        f"Language: {message.locale}\n\n"
        f"{message.message}\n"
    )
    _send(f"Website message ({message.topic}) from {message.name or message.email}", body,
          settings.STAFF_NOTIFICATION_EMAILS, reply_to=[message.email])
