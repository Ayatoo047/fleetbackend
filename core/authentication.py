from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from accounts.models import AuthToken


class BearerTokenAuthentication(BaseAuthentication):
    """`Authorization: Bearer <token>`, with tokens issued by `POST /auth/login`."""

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != b"bearer":
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("Invalid Authorization header.")
        try:
            raw = parts[1].decode()
        except UnicodeError as error:
            raise AuthenticationFailed("Invalid Authorization header.") from error

        token = (
            AuthToken.objects.select_related("user")
            .filter(key_hash=AuthToken.hash(raw), expires_at__gt=timezone.now())
            .first()
        )
        if token is None or not token.user.is_active:
            raise AuthenticationFailed("Invalid or expired token.")
        return token.user, token

    def authenticate_header(self, request):
        # Makes DRF answer 401 (not 403) when a token is missing or wrong.
        return 'Bearer realm="api"'
