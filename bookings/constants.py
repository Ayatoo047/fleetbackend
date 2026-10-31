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

CONTACT_TOPICS = ("general", "booking", "rental", "driver", "partner", "business", "cargo")
MESSAGE_STATUSES = ("new", "handled")

# Cargo quote requests and job applications ("leads").
LEAD_STATUSES = ("new", "in_progress", "closed")
SHIPPING_DIRECTIONS = ("ng_pl", "pl_ng")
GOODS_TYPES = ("food", "personal", "documents", "other")
JOB_ROLES = ("taxi", "courier")
WORK_STATUSES = ("eu", "permit", "student", "needs_permit")
AVAILABILITY = ("full_time", "part_time", "weekends")
