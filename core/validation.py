"""
Small validation helpers that report errors as the short codes the frontend understands
(`required`, `tooLong`, `email`, `invalid`, …), keyed by dot paths such as `pickup.city`.
"""

import datetime as dt
import re
from decimal import Decimal, InvalidOperation

import nh3
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .exceptions import Invalid

MISSING = object()


class FieldError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Checker:
    """Collects cleaned values and the first error code per field."""

    def __init__(self, data):
        self.data = data if isinstance(data, dict) else {}
        self.errors = {}

    def get(self, key, source=None):
        source = self.data if source is None else source
        return source.get(key, MISSING) if isinstance(source, dict) else MISSING

    def run(self, path, fn, value, *args, **kwargs):
        try:
            return fn(value, *args, **kwargs)
        except FieldError as error:
            self.fail(path, error.code)
            return None

    def fail(self, path, code):
        self.errors.setdefault(path, code)

    def raise_if_invalid(self):
        if self.errors:
            raise Invalid(self.errors)


def text(value, max_length, required=True):
    if value is MISSING or value is None:
        if required:
            raise FieldError("required")
        return ""
    if not isinstance(value, str):
        raise FieldError("invalid")
    value = value.strip()
    if required and not value:
        raise FieldError("required")
    if len(value) > max_length:
        raise FieldError("tooLong")
    return value


def pattern(value, regex, code, required=True):
    value = text(value, 1000, required=required)
    if value and not re.fullmatch(regex, value):
        raise FieldError(code)
    return value


def email(value):
    value = text(value, 254)
    try:
        validate_email(value)
    except ValidationError as error:
        raise FieldError("email") from error
    return value


def choice(value, choices, default=MISSING):
    if (value is MISSING or value is None or value == "") and default is not MISSING:
        return default
    if value not in choices:
        raise FieldError("invalid")
    return value


def integer(value, minimum, maximum, code="invalid", default=MISSING):
    """An integer in range. Accepts whole numbers sent as JSON numbers or numeric strings."""
    if (value is MISSING or value is None or value == "") and default is not MISSING:
        return default
    if isinstance(value, bool):
        raise FieldError(code)
    if isinstance(value, str):
        value = value.strip()
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise FieldError(code) from error
    if not number.is_integer() or not minimum <= number <= maximum:
        raise FieldError(code)
    return int(number)


def number(value, minimum, maximum, code="invalid", default=MISSING):
    """A number in range (decimals allowed), as a Decimal rounded to 2 places."""
    if (value is MISSING or value is None or value == "") and default is not MISSING:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise FieldError(code)
    try:
        result = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise FieldError(code) from error
    if not result.is_finite() or not minimum <= result <= maximum:
        raise FieldError(code)
    return result.quantize(Decimal("0.01"))


def boolean(value, default=MISSING):
    if value is MISSING and default is not MISSING:
        return default
    if not isinstance(value, bool):
        raise FieldError("invalid")
    return value


def iso_date(value, code="invalid"):
    """A real calendar date as "YYYY-MM-DD"."""
    value = text(value, 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise FieldError(code)
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise FieldError(code) from error


def image_url(value):
    """An uploaded image's URL, a site-relative path or ""."""
    value = text(value, 500, required=False)
    if value and not (value.startswith("/") or re.match(r"https?://", value)):
        raise FieldError("invalid")
    return value


SLUG_RE = r"[a-z0-9]+(?:-[a-z0-9]+)*"


def slug(value):
    if isinstance(value, str):
        value = value.strip().lower()
    value = text(value, 80)
    if not re.fullmatch(SLUG_RE, value):
        raise FieldError("invalid")
    return value


LOCALES = ("pl", "en")


def localized(check, field, max_length):
    """`{ pl, en }` plain text, both required. Errors go to `<field>.pl` / `<field>.en`."""
    raw = check.get(field)
    if not isinstance(raw, dict):
        for locale in LOCALES:
            check.fail(f"{field}.{locale}", "required")
        return None
    return {locale: check.run(f"{field}.{locale}", text, raw.get(locale, MISSING), max_length) for locale in LOCALES}


# Tags produced by the admin rich-text editor (Tiptap). See API.md, "Rich text".
RICH_TEXT_TAGS = {"p", "br", "h2", "h3", "strong", "b", "em", "i", "u", "s", "ul", "ol", "li", "blockquote", "a", "hr"}


def sanitize_html(html):
    return nh3.clean(
        html,
        tags=RICH_TEXT_TAGS,
        attributes={"a": {"href"}},
        url_schemes={"http", "https", "mailto", "tel"},
        link_rel="noopener noreferrer",
    )


def rich_text(check, field, max_length=200_000):
    """`{ pl, en }` HTML from the editor, sanitised, and with some visible text in both languages."""
    raw = check.get(field)
    if not isinstance(raw, dict):
        for locale in LOCALES:
            check.fail(f"{field}.{locale}", "required")
        return None
    cleaned = {}
    for locale in LOCALES:
        value = raw.get(locale, MISSING)
        if not isinstance(value, str):
            check.fail(f"{field}.{locale}", "required")
            continue
        if len(value) > max_length:
            check.fail(f"{field}.{locale}", "tooLong")
            continue
        html = sanitize_html(value.strip())
        if not nh3.clean(html, tags=set()).strip():
            check.fail(f"{field}.{locale}", "required")
            continue
        cleaned[locale] = html
    return cleaned if len(cleaned) == len(LOCALES) else None
