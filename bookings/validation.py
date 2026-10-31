"""
Validation for bookings and contact messages. Mirrors the frontend's Zod schemas
(`src/lib/booking/schema.ts`, `src/lib/contact/schema.ts`) and reports the same error codes.
"""

import datetime as dt

from core import validation as v
from core.utils import now_in_poland

from .constants import (
    AVAILABILITY,
    BOOKING_STATUSES,
    CONTACT_TOPICS,
    COUNTRIES,
    GOODS_TYPES,
    JOB_ROLES,
    LEAD_STATUSES,
    LOCALES,
    MESSAGE_STATUSES,
    SERVICE_TYPES,
    SHIPPING_DIRECTIONS,
    SPECIALIZED_TRANSPORT,
    WORK_STATUSES,
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


# Cargo quotes and job applications mirror the frontend's `src/lib/cargo/schema.ts` and
# `src/lib/careers/schema.ts`. A missing or unknown choice is reported as `required`, as there.


def _required_choice(value, options):
    if value not in options:
        raise v.FieldError("required")
    return value


def _required_phone(value):
    return _required(value, v.pattern, CONTACT_PHONE_RE, "phone", code="phone")


def validate_cargo_quote(data):
    check = v.Checker(data)
    get = check.get
    cleaned = {
        "name": check.run("name", v.text, get("name"), 200),
        "whatsapp": check.run("whatsapp", _required_phone, get("whatsapp")),
        "email": check.run("email", v.email, get("email")),
        "direction": check.run("direction", _required_choice, get("direction"), SHIPPING_DIRECTIONS),
        "goods_type": check.run("goodsType", _required_choice, get("goodsType"), GOODS_TYPES),
        "description": check.run("description", v.text, get("description"), 1000),
        "weight_kg": check.run("weightKg", v.number, get("weightKg"), 0, 100_000, "number", None),
        "destination_city": check.run("destinationCity", v.text, get("destinationCity"), 100, False),
        "notes": check.run("notes", v.text, get("notes"), 2000, False),
        "locale": get("locale") if get("locale") in LOCALES else "pl",
    }
    check.raise_if_invalid()
    # The destination city in Poland only applies to shipments going to Poland.
    if cleaned["direction"] == "pl_ng":
        cleaned["destination_city"] = ""
    return cleaned


def _licence(value):
    if not isinstance(value, bool):
        raise v.FieldError("required")
    return value


def validate_job_application(data):
    check = v.Checker(data)
    get = check.get
    cleaned = {
        "role": check.run("role", _required_choice, get("role"), JOB_ROLES),
        "name": check.run("name", v.text, get("name"), 200),
        "email": check.run("email", v.email, get("email")),
        "phone": check.run("phone", _required_phone, get("phone")),
        "city": check.run("city", v.text, get("city"), 100),
        "has_licence": check.run("hasLicence", _licence, get("hasLicence")),
        "work_status": check.run("workStatus", _required_choice, get("workStatus"), WORK_STATUSES),
        "availability": check.run("availability", _required_choice, get("availability"), AVAILABILITY),
        "message": check.run("message", v.text, get("message"), 3000, False),
        "locale": get("locale") if get("locale") in LOCALES else "pl",
    }
    check.raise_if_invalid()
    return cleaned


def validate_lead_update(data):
    check = v.Checker(data)
    status = check.run("status", v.choice, check.get("status"), LEAD_STATUSES)
    check.raise_if_invalid()
    return status
