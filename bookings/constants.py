"""Booking choices. Keep in line with the frontend's `src/lib/booking/constants.ts` and API.md."""

SERVICE_TYPES = ("city", "long_distance", "hourly")
SPECIALIZED_TRANSPORT = ("none", "airport", "wheelchair", "child_seat", "pet", "van", "executive")
BOOKING_STATUSES = ("new", "confirmed", "completed", "cancelled")
COUNTRIES = (
    "Poland",
    "Czech Republic",
    "Slovakia",
    "Germany",
    "Austria",
    "Hungary",
    "Ukraine",
    "Lithuania",
    "Other",
)
LOCALES = ("pl", "en")

CONTACT_TOPICS = ("general", "booking", "rental", "driver", "partner", "business")
MESSAGE_STATUSES = ("new", "handled")
