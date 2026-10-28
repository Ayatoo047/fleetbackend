"""JSON shapes and validation for services, rental cars and articles. Mirrors the admin forms' rules."""

from core import validation as v
from core.utils import iso

from .models import Article, FleetCar, Service


def _timestamps(obj):
    return {"createdAt": iso(obj.created_at), "updatedAt": iso(obj.updated_at)}


def service_to_json(s):
    return {
        "id": str(s.id),
        "slug": s.slug,
        "title": s.title,
        "summary": s.summary,
        "content": s.content,
        "image": s.image,
        "published": s.published,
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
        "slug": check.run("slug", v.slug, check.get("slug")),
        "title": v.localized(check, "title", 120),
        "summary": v.localized(check, "summary", 300),
        "content": v.rich_text(check, "content"),
        "image": check.run("image", v.image_url, check.get("image")),
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


def validate_article(data, instance=None):
    check = v.Checker(data)
    cleaned = {
        "slug": check.run("slug", v.slug, check.get("slug")),
        "title": v.localized(check, "title", 160),
        "summary": v.localized(check, "summary", 300),
        "body": v.rich_text(check, "body"),
        "cover_image": check.run("coverImage", v.image_url, check.get("coverImage")),
        "published": check.run("published", v.boolean, check.get("published"), False),
        "published_at": check.run("publishedAt", v.iso_date, check.get("publishedAt")),
    }
    _unique_slug(check, cleaned, Article, instance)
    check.raise_if_invalid()
    return cleaned
