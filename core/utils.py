import datetime as dt
from zoneinfo import ZoneInfo

from django.utils import timezone

POLAND = ZoneInfo("Europe/Warsaw")


def now_in_poland():
    return timezone.now().astimezone(POLAND)


def iso(value):
    """ISO 8601 in UTC with milliseconds, the same shape as JavaScript's `toISOString()`."""
    if value is None:
        return None
    return value.astimezone(dt.UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _positive_int(raw, default):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value >= 1 else default


def paginate(request, queryset, serialize, default_size=25, max_size=100):
    """`{ items, total, page, pageSize }` from the `page` and `pageSize` query parameters."""
    page = _positive_int(request.query_params.get("page"), 1)
    size = min(_positive_int(request.query_params.get("pageSize"), default_size), max_size)
    start = (page - 1) * size
    return {
        "items": [serialize(item) for item in queryset[start : start + size]],
        "total": queryset.count(),
        "page": page,
        "pageSize": size,
    }


def flag(request, name):
    return request.query_params.get(name, "").lower() in {"1", "true", "yes"}
