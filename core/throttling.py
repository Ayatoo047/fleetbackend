from django.conf import settings
from django.utils.crypto import constant_time_compare
from rest_framework.throttling import SimpleRateThrottle


def visitor_ip(request):
    """
    The website visitor's IP, as forwarded by the Next.js server.

    Browsers never call the API directly, so the connecting IP is the frontend server's.
    The frontend forwards the visitor's IP in `X-Visitor-Ip`; it is only trusted when the
    request also carries the shared `FRONTEND_API_KEY`.
    """
    key = settings.FRONTEND_API_KEY
    ip = request.headers.get("X-Visitor-Ip", "").strip()
    if key and ip and constant_time_compare(request.headers.get("X-Api-Key", ""), key):
        return ip[:64]
    return None


class VisitorRateThrottle(SimpleRateThrottle):
    """Limits anonymous requests per visitor. Requests with a valid admin token are never limited."""

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": visitor_ip(request) or self.get_ident(request)}


class BookingThrottle(VisitorRateThrottle):
    scope = "bookings"


class ContactThrottle(VisitorRateThrottle):
    scope = "contact"


class LoginThrottle(VisitorRateThrottle):
    scope = "login"


class EnquiryThrottle(VisitorRateThrottle):
    """Cargo quote requests and job applications."""

    scope = "enquiries"
