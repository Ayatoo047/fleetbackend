"""
Validation for bookings and contact messages. Mirrors the frontend's Zod schemas
(`src/lib/booking/schema.ts`, `src/lib/contact/schema.ts`) and reports the same error codes.
"""

import datetime as dt

from core import validation as v
from core.utils import now_in_poland

from .constants import (
    BOOKING_STATUSES,
    CONTACT_TOPICS,
    COUNTRIES,
    LOCALES,
    MESSAGE_STATUSES,
    SERVICE_TYPES,
    SPECIALIZED_TRANSPORT,
)

PHONE_RE = r"[\d\s()-]{6,20}"
AREA_CODE_RE = r"\+\d{1,4}"
TIME_RE = r"([01]\d|2[0-3]):[0-5]\d"
CONTACT_PHONE_RE = r"\+?[\d\s()-]{6,25}"


def _service_types(value):
    if not isinstance(value, list):
        raise v.FieldError("serviceRequired" if value in (v.MISSING, None) else "invalid")
    if not value:
        raise v.FieldError("serviceRequired")
    if any(item not in SERVICE_TYPES for item in value):
        raise v.FieldError("invalid")
    return list(dict.fromkeys(value))


def _required(value, fn, *args, code):
    """Runs `fn`, reporting a missing or blank value as `required` and anything else as `code`."""
    if value in (v.MISSING, None) or (isinstance(value, str) and not value.strip()):
        raise v.FieldError("required")
    try:
        return fn(value, *args)
    except v.FieldError as error:
        raise v.FieldError("tooLong" if error.code == "tooLong" else code) from error


def _date(value):
    return _required(value, v.iso_date, code="date")


def _time(value):
    value = _required(value, v.pattern, TIME_RE, "time", code="time")
    return dt.time.fromisoformat(value)


def _address(check, prefix, required):
    raw = check.get(prefix)
    raw = raw if isinstance(raw, dict) else {}

    def part(key, max_length, required=False):
        return check.run(f"{prefix}.{key}", v.text, raw.get(key, v.MISSING), max_length, required)

    return {
        "street": part("street", 200, required),
        "city": part("city", 100, required),
        "state": part("state", 100),
        "postal_code": part("postalCode", 20),
        "country": check.run(f"{prefix}.country", v.choice, raw.get("country", v.MISSING), COUNTRIES, "Poland"),
    }


def validate_booking(data, allow_past=False):
    """
    Validates a full `BookingPayload` and returns model field values.

    `allow_past` is used for staff: they may enter or edit rides in the past (e.g. to log a
    completed ride). Customers on the website may not.
    """
    check = v.Checker(data)
    get = check.get
    cleaned = {
        "service_types": check.run("serviceTypes", _service_types, get("serviceTypes")),
        "specialized_transport": check.run(
            "specializedTransport", v.choice, get("specializedTransport"), SPECIALIZED_TRANSPORT, "none"
        ),
        "first_name": check.run("firstName", v.text, get("firstName"), 100),
        "last_name": check.run("lastName", v.text, get("lastName"), 100),
        "phone_country_code": check.run(
            "phoneCountryCode", v.pattern, get("phoneCountryCode"), AREA_CODE_RE, "areaCode", False
        ),
        "phone": check.run("phone", _required, get("phone"), v.pattern, PHONE_RE, "phone", code="phone"),
        "email": check.run("email", v.email, get("email")),
        "date": check.run("date", _date, get("date")),
        "time": check.run("time", _time, get("time")),
        "pickup": _address(check, "pickup", required=True),
        "dropoff": _address(check, "dropoff", required=False),
        "passengers": check.run("passengers", v.integer, get("passengers"), 1, 50, "passengers"),
        "luggage_kg": check.run("luggageKg", v.integer, get("luggageKg"), 0, 1000, "luggage", None),
        "notes": check.run("notes", v.text, get("notes"), 2000, False),
        # Not a form field, so an unexpected value falls back to Polish rather than failing.
        "locale": get("locale") if get("locale") in LOCALES else "pl",
    }
    if cleaned["phone_country_code"] == "" and "phoneCountryCode" not in check.errors:
        check.fail("phoneCountryCode", "areaCode")

    # A drop-off address is only optional when every selected service is hourly.
    services = cleaned["service_types"] or []
    if not (services and all(s == "hourly" for s in services)):
        for part in ("street", "city"):
            if cleaned["dropoff"][part] == "" and f"dropoff.{part}" not in check.errors:
                check.fail(f"dropoff.{part}", "required")

    if not allow_past and cleaned["date"] and cleaned["time"]:
        now = now_in_poland()
        if (cleaned["date"], cleaned["time"]) <= (now.date(), now.time().replace(second=0, microsecond=0)):
            check.fail("date", "datePast")

    check.raise_if_invalid()
    return cleaned


def validate_booking_admin_fields(data):
    """`status` and `adminNotes`, which only staff can set."""
    check = v.Checker(data)
    cleaned = {}
    if "status" in check.data:
        cleaned["status"] = check.run("status", v.choice, check.data["status"], BOOKING_STATUSES)
    if "adminNotes" in check.data:
        cleaned["admin_notes"] = check.run("adminNotes", v.text, check.data["adminNotes"], 5000, False)
    check.raise_if_invalid()
    return cleaned


def _contact_phone(value):
    value = v.text(value, 30, required=False)
    if value:
        try:
            v.pattern(value, CONTACT_PHONE_RE, "phone")
        except v.FieldError as error:
            raise v.FieldError("phone") from error
    return value


def validate_contact(data):
    check = v.Checker(data)
    get = check.get
    cleaned = {
        "name": check.run("name", v.text, get("name"), 200, False),
        "email": check.run("email", v.email, get("email")),
        "phone": check.run("phone", _contact_phone, get("phone")),
        "topic": check.run("topic", v.choice, get("topic"), CONTACT_TOPICS, "general"),
        "message": check.run("message", v.text, get("message"), 5000),
        "locale": get("locale") if get("locale") in LOCALES else "pl",
    }
    check.raise_if_invalid()
    return cleaned


def validate_message_update(data):
    check = v.Checker(data)
    status = check.run("status", v.choice, check.get("status"), MESSAGE_STATUSES)
    check.raise_if_invalid()
    return status
