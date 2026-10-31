import json
import logging
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """
    Sends plain-text email through Resend's HTTP API (https://resend.com/docs/api-reference/emails/send-email).
    Used when RESEND_API_KEY is set. HTTPS works on hosts that block outgoing SMTP ports.
    """

    url = "https://api.resend.com/emails"

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            payload = {
                "from": message.from_email,
                "to": message.to,
                "cc": message.cc,
                "bcc": message.bcc,
                "reply_to": message.reply_to,
                "subject": message.subject,
                "text": message.body,
            }
            request = urllib.request.Request(
                self.url,
                data=json.dumps({k: v for k, v in payload.items() if v}).encode(),
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "fleetflow-backend",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=settings.EMAIL_TIMEOUT):
                    sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception("Resend could not send %r", message.subject)
        return sent
