"""JSON shapes and validation for services, rental cars, FAQ entries and site settings. Mirrors the admin forms' rules."""

from core import validation as v
from core.utils import iso

from .models import BRANDS, FAQ_CATEGORIES, Faq, FleetCar, Service, SiteSettings


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
        "color": c.color,
        "fuel": c.fuel,
        "summary": c.summary,
        "features": c.features,
        "published": c.published,
        "sortOrder": c.sort_order,
        **_timestamps(c),
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
    check.raise_if_invalid()
    cleaned["color"] = cleaned["color"].lower()
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
    check.raise_if_invalid()
    return cleaned


def save_settings(cleaned):
    settings = SiteSettings.load()
    for field, value in cleaned.items():
        setattr(settings, field, value)
    settings.save()
    return settings
