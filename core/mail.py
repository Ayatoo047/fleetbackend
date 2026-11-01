import json
import logging
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


def _address(value):
    """`"Name <a@example.com>"` or `"a@example.com"` → ZeptoMail's `{ address, name }`."""
    name, address = parseaddr(value)
    return {"address": address, "name": name} if name else {"address": address}


def _recipients(values):
    return [{"email_address": _address(value)} for value in values]


class ZeptoMailEmailBackend(BaseEmailBackend):
    """
    Sends plain-text email through ZeptoMail's API (`POST /v1.1/email`). Used when ZEPTOMAIL_TOKEN is set.
    HTTPS works on hosts that block outgoing SMTP ports.
    """

    def send_messages(self, email_messages):
        token = settings.ZEPTOMAIL_TOKEN
        # The dashboard shows the token with its scheme ("Zoho-enczapikey …"); accept it with or without.
        if not token.startswith("Zoho-enczapikey "):
            token = f"Zoho-enczapikey {token}"
        sent = 0
        for message in email_messages:
            payload = {
                "from": _address(message.from_email),
                "to": _recipients(message.to),
                "cc": _recipients(message.cc),
                "bcc": _recipients(message.bcc),
                "reply_to": [_address(value) for value in message.reply_to],
                "subject": message.subject,
                "textbody": message.body,
            }
            request = urllib.request.Request(
                f"https://{settings.ZEPTOMAIL_API_HOST}/v1.1/email",
                data=json.dumps({k: v for k, v in payload.items() if v}).encode(),
                headers={"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=settings.EMAIL_TIMEOUT):
                    sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception("ZeptoMail could not send %r", message.subject)
        return sent
