"""JSON shapes and validation for services, rental cars, news articles, FAQ entries and site settings. Mirrors the admin forms' rules."""

from core import validation as v
from core.utils import iso

from .models import BANNER_TONES, BRANDS, FAQ_CATEGORIES, Article, DayTrip, Faq, FleetCar, Service, SiteSettings


def _timestamps(obj):
    return {"createdAt": iso(obj.created_at), "updatedAt": iso(obj.updated_at)}


def service_to_json(s):
    return {
        "id": str(s.id),
        "brand": s.brand,
        "slug": s.slug,
        "title": s.title,
        "summary": s.summary,
        "content": s.content,
        "image": s.image,
        "published": s.published,
        "comingSoon": s.coming_soon,
        "sortOrder": s.sort_order,
        **_timestamps(s),
    }


def car_to_json(c):
    return {
        "id": str(c.id),
        "name": c.name,
        "year": c.year,
        "pricePerWeek": c.price_per_week,
        "image": c.image,
        "gallery": c.gallery or [],
        "color": c.color,
        "fuel": c.fuel,
        "summary": c.summary,
        "features": c.features,
        "published": c.published,
        "sortOrder": c.sort_order,
        **_timestamps(c),
    }


def article_to_json(a):
    return {
        "id": str(a.id),
        "slug": a.slug,
        "title": a.title,
        "summary": a.summary,
        "body": a.body,
        "coverImage": a.cover_image,
        "published": a.published,
        "publishedAt": a.published_at.isoformat(),
        **_timestamps(a),
    }


def day_trip_to_json(t):
    return {
        "id": str(t.id),
        "slug": t.slug,
        "name": t.name,
        "text": t.text,
        "distance": t.distance,
        "duration": t.duration,
        "photo": t.photo,
        "photoAlt": t.photo_alt,
        "photoCredit": t.photo_credit,
        "destination": t.destination,
        "published": t.published,
        "sortOrder": t.sort_order,
        **_timestamps(t),
    }


def faq_to_json(f):
    return {
        "id": str(f.id),
        "category": f.category,
        "question": f.question,
        "answer": f.answer,
        "published": f.published,
        "sortOrder": f.sort_order,
        **_timestamps(f),
    }


def settings_to_json(st):
    return {
        "cargoRatePerKg": float(st.cargo_rate_per_kg),
        "cargoMinWeightKg": float(st.cargo_min_weight_kg),
        "cargoEstimatorEnabled": st.cargo_estimator_enabled,
        "rentalPromoEnabled": st.rental_promo_enabled,
        "rentalFirstWeekDiscountPercent": st.rental_first_week_discount_percent,
        "contactPhone": st.contact_phone,
        "contactEmail": st.contact_email,
        "contactWhatsapp": st.contact_whatsapp,
        "cargoWhatsapp": st.cargo_whatsapp,
        "cargoEmail": st.cargo_email,
        "bannerEnabled": st.banner_enabled,
        "bannerText": st.banner_text,
        "bannerTone": st.banner_tone,
    }


def _unique_slug(check, cleaned, model, instance):
    if cleaned.get("slug"):
        taken = model.objects.filter(slug=cleaned["slug"])
        if instance is not None:
            taken = taken.exclude(pk=instance.pk)
        if taken.exists():
            check.fail("slug", "taken")


def _common(check):
    return {
        "published": check.run("published", v.boolean, check.get("published"), False),
        "sort_order": check.run("sortOrder", v.integer, check.get("sortOrder"), 0, 999, "invalid", 0),
    }


def validate_service(data, instance=None):
    check = v.Checker(data)
    cleaned = {
        "brand": check.run("brand", v.choice, check.get("brand"), BRANDS),
        "slug": check.run("slug", v.slug, check.get("slug")),
        "title": v.localized(check, "title", 120),
        "summary": v.localized(check, "summary", 300),
        "content": v.rich_text(check, "content"),
        "image": check.run("image", v.image_url, check.get("image")),
        "coming_soon": check.run("comingSoon", v.boolean, check.get("comingSoon"), False),
        **_common(check),
    }
    _unique_slug(check, cleaned, Service, instance)
    check.raise_if_invalid()
    return cleaned


def _features(check):
    raw = check.get("features")
    raw = raw if isinstance(raw, dict) else {}
    cleaned = {}
    for locale in v.LOCALES:
        items = raw.get(locale, [])
        path = f"features.{locale}"
        if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
            check.fail(path, "invalid")
            continue
        items = [i.strip() for i in items if i.strip()]
        if len(items) > 12 or any(len(i) > 120 for i in items):
            check.fail(path, "tooLong")
            continue
        cleaned[locale] = items
    return cleaned


MAX_GALLERY = 8


def _gallery(check):
    """Optional list of image URLs; older clients don't send it, which keeps the current photos."""
    raw = check.get("gallery")
    if raw is v.MISSING or raw is None:
        return None
    if not isinstance(raw, list):
        check.fail("gallery", "invalid")
        return None
    if len(raw) > MAX_GALLERY:
        check.fail("gallery", "tooLong")
        return None
    cleaned = []
    for i, url in enumerate(raw):
        value = check.run(f"gallery.{i}", v.image_url, url)
        if value:
            cleaned.append(value)
    return cleaned


def validate_car(data, instance=None):
    check = v.Checker(data)
    cleaned = {
        "name": check.run("name", v.text, check.get("name"), 80),
        "year": check.run("year", v.integer, check.get("year"), 1990, 2100),
        "price_per_week": check.run("pricePerWeek", v.integer, check.get("pricePerWeek"), 0, 100_000),
        "image": check.run("image", v.image_url, check.get("image")),
        "color": check.run("color", v.pattern, check.get("color"), r"#[0-9a-fA-F]{6}", "invalid"),
        "fuel": v.localized(check, "fuel", 40),
        "summary": v.localized(check, "summary", 300),
        "features": _features(check),
        **_common(check),
    }
    gallery = _gallery(check)
    check.raise_if_invalid()
    cleaned["color"] = cleaned["color"].lower()
    if gallery is not None:
        cleaned["gallery"] = gallery
    elif instance is None:
        cleaned["gallery"] = []
    return cleaned


def validate_article(data, instance=None):
    check = v.Checker(data)
    cleaned = {
        "slug": check.run("slug", v.slug, check.get("slug")),
        "title": v.localized(check, "title", 200),
        "summary": v.localized(check, "summary", 500),
        "body": v.rich_text(check, "body"),
        "cover_image": check.run("coverImage", v.image_url, check.get("coverImage")),
        "published": check.run("published", v.boolean, check.get("published"), False),
        "published_at": check.run("publishedAt", v.iso_date, check.get("publishedAt"), "date"),
    }
    _unique_slug(check, cleaned, Article, instance)
    check.raise_if_invalid()
    return cleaned


def _plain_localized(check, field, max_length):
    """`{ pl, en }` plain text where both may be empty."""
    raw = check.get(field)
    if raw is v.MISSING or raw is None:
        return {"pl": "", "en": ""}
    if not isinstance(raw, dict):
        check.fail(field, "invalid")
        return None
    return {
        locale: check.run(f"{field}.{locale}", v.text, raw.get(locale, ""), max_length, required=False)
        for locale in v.LOCALES
    }


def _credit(check):
    raw = check.get("photoCredit")
    raw = raw if isinstance(raw, dict) else {}
    source = check.run("photoCredit.source", v.pattern, raw.get("source", ""), r"https?://\S+", "invalid", required=False)
    if source and len(source) > 500:
        check.fail("photoCredit.source", "tooLong")
    return {
        "author": check.run("photoCredit.author", v.text, raw.get("author", ""), 120, required=False),
        "license": check.run("photoCredit.license", v.text, raw.get("license", ""), 60, required=False),
        "source": source or "",
    }


def _destination(check):
    raw = check.get("destination")
    raw = raw if isinstance(raw, dict) else {}
    return {
        "street": check.run("destination.street", v.text, raw.get("street", ""), 200, required=False),
        "city": check.run("destination.city", v.text, raw.get("city", v.MISSING), 100),
        "postalCode": check.run("destination.postalCode", v.text, raw.get("postalCode", ""), 20, required=False),
    }


def validate_day_trip(data, instance=None):
    check = v.Checker(data)
    cleaned = {
        "slug": check.run("slug", v.slug, check.get("slug")),
        "name": v.localized(check, "name", 120),
        "text": v.localized(check, "text", 500),
        "distance": v.localized(check, "distance", 40),
        "duration": v.localized(check, "duration", 40),
        "photo": check.run("photo", v.image_url, check.get("photo")),
        "photo_alt": _plain_localized(check, "photoAlt", 200),
        "photo_credit": _credit(check),
        "destination": _destination(check),
        **_common(check),
    }
    _unique_slug(check, cleaned, DayTrip, instance)
    check.raise_if_invalid()
    return cleaned


def validate_faq(data, instance=None):
    check = v.Checker(data)
    cleaned = {
        "category": check.run("category", v.choice, check.get("category"), FAQ_CATEGORIES),
        "question": v.localized(check, "question", 200),
        "answer": v.rich_text(check, "answer"),
        **_common(check),
    }
    check.raise_if_invalid()
    return cleaned


def validate_settings(data):
    check = v.Checker(data)
    cleaned = {
        "cargo_rate_per_kg": check.run("cargoRatePerKg", v.number, check.get("cargoRatePerKg"), 0, 10_000),
        "cargo_min_weight_kg": check.run("cargoMinWeightKg", v.number, check.get("cargoMinWeightKg"), 0, 1000),
        "cargo_estimator_enabled": check.run("cargoEstimatorEnabled", v.boolean, check.get("cargoEstimatorEnabled")),
    }
    # Added in November 2026; older admin forms don't send them, which keeps the stored values.
    if check.get("rentalPromoEnabled") is not v.MISSING:
        cleaned["rental_promo_enabled"] = check.run("rentalPromoEnabled", v.boolean, check.get("rentalPromoEnabled"))
    if check.get("rentalFirstWeekDiscountPercent") is not v.MISSING:
        cleaned["rental_first_week_discount_percent"] = check.run(
            "rentalFirstWeekDiscountPercent", v.integer, check.get("rentalFirstWeekDiscountPercent"), 0, 90
        )
    # Contact details and the banner (also added in November 2026); likewise optional.
    for key, field, fn, args in [
        ("contactPhone", "contact_phone", v.pattern, (PHONE_RE, "phone", False)),
        ("contactWhatsapp", "contact_whatsapp", v.pattern, (PHONE_RE, "phone", False)),
        ("cargoWhatsapp", "cargo_whatsapp", v.pattern, (PHONE_RE, "phone", False)),
        ("contactEmail", "contact_email", _optional_email, ()),
        ("cargoEmail", "cargo_email", _optional_email, ()),
        ("bannerEnabled", "banner_enabled", v.boolean, ()),
        ("bannerTone", "banner_tone", v.choice, (BANNER_TONES,)),
    ]:
        if check.get(key) is not v.MISSING:
            cleaned[field] = check.run(key, fn, check.get(key), *args)
    if check.get("bannerText") is not v.MISSING:
        cleaned["banner_text"] = _plain_localized(check, "bannerText", 300)
    enabled = cleaned.get("banner_enabled", MISSING_SETTING)
    if enabled is MISSING_SETTING:
        enabled = SiteSettings.load().banner_enabled
    if enabled and cleaned.get("banner_text", True) is not None:
        text = cleaned["banner_text"] if "banner_text" in cleaned else SiteSettings.load().banner_text
        for locale in v.LOCALES:
            if not text.get(locale):
                check.fail(f"bannerText.{locale}", "required")
    check.raise_if_invalid()
    return cleaned


MISSING_SETTING = object()
PHONE_RE = r"\+?[0-9][0-9 ()\-]{5,30}"


def _optional_email(value):
    if value in ("", None):
        return ""
    return v.email(value)


def save_settings(cleaned):
    settings = SiteSettings.load()
    for field, value in cleaned.items():
        setattr(settings, field, value)
    settings.save()
    return settings
