"""End-to-end checks of the API contract in the frontend's API.md."""

import datetime as dt
import shutil
import tempfile
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import AuthToken, User
from bookings.models import Booking, CargoQuote, ContactMessage, JobApplication
from content.models import Faq, FleetCar, Service, SiteSettings
from core.utils import now_in_poland

TEMP_MEDIA = tempfile.mkdtemp()


def future_date(days=3):
    return (now_in_poland().date() + dt.timedelta(days=days)).isoformat()


def booking_payload(**overrides):
    payload = {
        "serviceTypes": ["city"],
        "specializedTransport": "none",
        "firstName": "Anna",
        "lastName": "Nowak",
        "phoneCountryCode": "+48",
        "phone": "600 100 200",
        "email": "anna@example.com",
        "date": future_date(),
        "time": "09:30",
        "pickup": {"street": "Rynek 1", "city": "Kraków", "state": "", "postalCode": "31-000", "country": "Poland"},
        "dropoff": {"street": "Lotnisko", "city": "Balice", "state": "", "postalCode": "", "country": "Poland"},
        "passengers": 2,
        "luggageKg": None,
        "notes": "",
        "locale": "pl",
    }
    payload.update(overrides)
    return payload


def service_payload(**overrides):
    payload = {
        "brand": "cargo",
        "slug": "van-cargo",
        "title": {"pl": "Bus", "en": "Van"},
        "summary": {"pl": "Przewóz", "en": "Cargo"},
        "content": {"pl": "<p>Treść</p>", "en": "<p>Body <script>alert(1)</script></p>"},
        "image": "",
        "published": True,
        "comingSoon": False,
        "sortOrder": 1,
    }
    payload.update(overrides)
    return payload


@override_settings(
    STAFF_NOTIFICATION_EMAILS=["staff@example.com"],
    FRONTEND_API_KEY="secret",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class ApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = User.objects.create_user("admin@example.com", "admin-password", name="Admin", role="admin")
        self.staff = User.objects.create_user("staff@example.com", "staff-password", name="Staff", role="staff")

    def login(self, email="admin@example.com", password="admin-password"):
        response = self.client.post("/v1/auth/login", {"email": email, "password": password}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["token"]

    def as_user(self, email="admin@example.com", password="admin-password"):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.login(email, password)}")
        return client


class AuthTests(ApiTestCase):
    def test_login(self):
        response = self.client.post("/v1/auth/login", {"email": "ADMIN@example.com", "password": "admin-password"}, format="json")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["expiresIn"], 8 * 3600)
        self.assertEqual(body["user"], {"id": str(self.admin.id), "email": "admin@example.com", "name": "Admin", "role": "admin"})
        self.admin.refresh_from_db()
        self.assertIsNotNone(self.admin.last_login)
        self.assertFalse(AuthToken.objects.filter(key_hash=body["token"]).exists(), "tokens are stored hashed")

    def test_wrong_credentials(self):
        self.assertEqual(self.client.post("/v1/auth/login", {"email": "admin@example.com", "password": "nope"}, format="json").status_code, 401)
        self.assertEqual(self.client.post("/v1/auth/login", {}, format="json").status_code, 400)

    def test_admin_endpoints_need_a_valid_token(self):
        self.assertEqual(self.client.get("/v1/bookings").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer wrong")
        self.assertEqual(self.client.get("/v1/bookings").status_code, 401)

    def test_expired_token(self):
        client = self.as_user()
        AuthToken.objects.update(expires_at=now_in_poland() - dt.timedelta(seconds=1))
        self.assertEqual(client.get("/v1/bookings").status_code, 401)

    def test_inactive_user(self):
        client = self.as_user()
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        self.assertEqual(client.get("/v1/bookings").status_code, 401)

    def test_login_rate_limit(self):
        from rest_framework.throttling import SimpleRateThrottle

        with mock.patch.object(SimpleRateThrottle, "THROTTLE_RATES", {"login": "2/hour"}):
            codes = [self.client.post("/v1/auth/login", {"email": "x@example.com", "password": "x"}, format="json").status_code for _ in range(3)]
        self.assertEqual(codes, [401, 401, 429])


class BookingTests(ApiTestCase):
    def test_create_booking(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post("/v1/bookings", booking_payload(), format="json")
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertRegex(body["reference"], r"^FF-[2-9A-HJ-NP-Z]{6}$")
        booking = Booking.objects.get(pk=body["id"])
        self.assertEqual(booking.status, "new")
        self.assertEqual(booking.pickup_city, "Kraków")
        # Staff notification and the Polish customer confirmation.
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["staff@example.com"])
        self.assertEqual(mail.outbox[1].to, ["anna@example.com"])
        self.assertIn(body["reference"], mail.outbox[1].subject)
        self.assertIn("Dzień dobry", mail.outbox[1].body)

    def test_validation_errors_use_frontend_codes(self):
        payload = booking_payload(
            serviceTypes=[],
            firstName=" ",
            phoneCountryCode="48",
            phone="abc",
            email="not-an-email",
            date="2025-02-30",
            time="25:00",
            passengers=0,
            luggageKg=5000,
            notes="x" * 2001,
            pickup={"street": "", "city": "", "country": "Mars"},
            dropoff={"street": "", "city": ""},
        )
        response = self.client.post("/v1/bookings", payload, format="json")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["errors"],
            {
                "serviceTypes": "serviceRequired",
                "firstName": "required",
                "phoneCountryCode": "areaCode",
                "phone": "phone",
                "email": "email",
                "date": "date",
                "time": "time",
                "pickup.street": "required",
                "pickup.city": "required",
                "pickup.country": "invalid",
                "passengers": "passengers",
                "luggageKg": "luggage",
                "notes": "tooLong",
                # No service selected counts as "not hourly-only", as in the frontend schema.
                "dropoff.street": "required",
                "dropoff.city": "required",
            },
        )

    def test_dropoff_required_unless_hourly_only(self):
        no_dropoff = {"street": "", "city": "", "state": "", "postalCode": "", "country": "Poland"}
        response = self.client.post("/v1/bookings", booking_payload(dropoff=no_dropoff), format="json")
        self.assertEqual(response.json()["errors"], {"dropoff.street": "required", "dropoff.city": "required"})
        response = self.client.post("/v1/bookings", booking_payload(serviceTypes=["hourly"], dropoff=no_dropoff), format="json")
        self.assertEqual(response.status_code, 201)

    def test_past_dates_rejected_for_customers_but_allowed_for_staff(self):
        yesterday = (now_in_poland().date() - dt.timedelta(days=1)).isoformat()
        response = self.client.post("/v1/bookings", booking_payload(date=yesterday), format="json")
        self.assertEqual(response.json()["errors"], {"date": "datePast"})
        with self.captureOnCommitCallbacks(execute=True):
            response = self.as_user().post("/v1/bookings", booking_payload(date=yesterday), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 0, "phone bookings entered by staff send no emails")

    def test_rate_limit_per_visitor_and_not_for_staff(self):
        from rest_framework.throttling import SimpleRateThrottle

        with mock.patch.object(SimpleRateThrottle, "THROTTLE_RATES", {"bookings": "1/hour", "login": "100/hour"}):
            headers = {"HTTP_X_API_KEY": "secret"}
            first = self.client.post("/v1/bookings", booking_payload(), format="json", HTTP_X_VISITOR_IP="1.1.1.1", **headers)
            second = self.client.post("/v1/bookings", booking_payload(), format="json", HTTP_X_VISITOR_IP="1.1.1.1", **headers)
            other = self.client.post("/v1/bookings", booking_payload(), format="json", HTTP_X_VISITOR_IP="2.2.2.2", **headers)
            staff = self.as_user()
            staff_codes = [staff.post("/v1/bookings", booking_payload(), format="json").status_code for _ in range(3)]
        self.assertEqual([first.status_code, second.status_code, other.status_code], [201, 429, 201])
        self.assertEqual(staff_codes, [201, 201, 201])

    def test_visitor_ip_ignored_without_the_api_key(self):
        from rest_framework.throttling import SimpleRateThrottle

        with mock.patch.object(SimpleRateThrottle, "THROTTLE_RATES", {"bookings": "1/hour"}):
            first = self.client.post("/v1/bookings", booking_payload(), format="json", HTTP_X_VISITOR_IP="1.1.1.1")
            second = self.client.post("/v1/bookings", booking_payload(), format="json", HTTP_X_VISITOR_IP="2.2.2.2")
        self.assertEqual([first.status_code, second.status_code], [201, 429])

    def make_booking(self, **overrides):
        response = self.client.post("/v1/bookings", booking_payload(**overrides), format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return Booking.objects.get(pk=response.json()["id"])

    def test_list_search_filter_and_pagination(self):
        a = self.make_booking(firstName="Jan", lastName="Kowalski", date=future_date(5))
        b = self.make_booking(email="piotr@example.com", date=future_date(1))
        c = self.make_booking(pickup={"street": "Piotrkowska 1", "city": "Łódź", "country": "Poland"}, date=future_date(2))
        Booking.objects.filter(pk=c.pk).update(status="confirmed", date=now_in_poland().date() - dt.timedelta(days=3))
        client = self.as_user("staff@example.com", "staff-password")

        body = client.get("/v1/bookings").json()
        self.assertEqual(body["total"], 3)
        self.assertEqual([i["id"] for i in body["items"]], [str(c.id), str(b.id), str(a.id)])
        self.assertEqual(set(body["items"][0]), {
            "id", "reference", "status", "adminNotes", "createdAt", "updatedAt", "serviceTypes",
            "specializedTransport", "firstName", "lastName", "phoneCountryCode", "phone", "email", "date", "time",
            "pickup", "dropoff", "passengers", "luggageKg", "notes", "locale",
        })

        self.assertEqual([i["id"] for i in client.get("/v1/bookings", {"q": "jan kowal"}).json()["items"]], [str(a.id)])
        self.assertEqual([i["id"] for i in client.get("/v1/bookings", {"q": "PIOTR"}).json()["items"]], [str(b.id)])
        self.assertEqual([i["id"] for i in client.get("/v1/bookings", {"q": "Łódź"}).json()["items"]] , [str(c.id)])
        self.assertEqual(client.get("/v1/bookings", {"q": c.reference}).json()["total"], 1)
        self.assertEqual([i["id"] for i in client.get("/v1/bookings", {"status": "confirmed"}).json()["items"]], [str(c.id)])
        self.assertEqual([i["id"] for i in client.get("/v1/bookings", {"upcoming": "true"}).json()["items"]], [str(b.id), str(a.id)])

        page = client.get("/v1/bookings", {"page": 2, "pageSize": 2}).json()
        self.assertEqual((page["total"], page["page"], page["pageSize"], len(page["items"])), (3, 2, 2, 1))

    def test_stats(self):
        self.make_booking()
        today = self.make_booking(date=future_date(0), time="23:59") if now_in_poland().strftime("%H:%M") < "23:59" else None
        Booking.objects.filter(pk=self.make_booking().pk).update(status="cancelled")
        body = self.as_user().get("/v1/bookings/stats").json()
        new = 2 if today else 1
        self.assertEqual(body["counts"], {"new": new, "confirmed": 0, "completed": 0, "cancelled": 1})
        self.assertEqual(body["today"], 1 if today else 0)

    def test_get_patch_delete(self):
        booking = self.make_booking()
        client = self.as_user()
        url = f"/v1/bookings/{booking.id}"
        self.assertEqual(client.get(url).json()["reference"], booking.reference)

        response = client.patch(url, {"status": "confirmed", "adminNotes": "Called back"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()["status"], response.json()["adminNotes"]), ("confirmed", "Called back"))

        full = {**client.get(url).json(), "firstName": "Zofia", "date": "2020-01-01", "status": "completed"}
        response = client.patch(url, full, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()["firstName"], response.json()["date"]), ("Zofia", "2020-01-01"))

        self.assertEqual(client.patch(url, {"status": "lost"}, format="json").json(), {"errors": {"status": "invalid"}})
        self.assertEqual(client.patch(url, {"serviceTypes": ["city"], "dropoff": {"street": "", "city": ""}}, format="json").status_code, 422)

        self.assertEqual(client.delete(url).status_code, 204)
        self.assertEqual(client.get(url).status_code, 404)
        self.assertEqual(client.get("/v1/bookings/not-a-uuid").status_code, 404)


class ContactMessageTests(ApiTestCase):
    def test_send_and_manage(self):
        payload = {"name": "", "email": "jan@example.com", "phone": "", "topic": "cargo", "message": "Hello", "locale": "en"}
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post("/v1/contact-messages", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)

        bad = {**payload, "email": "x", "phone": "abc", "topic": "spam", "message": "y" * 5001}
        self.assertEqual(
            self.client.post("/v1/contact-messages", bad, format="json").json(),
            {"errors": {"email": "email", "phone": "phone", "topic": "invalid", "message": "tooLong"}},
        )

        client = self.as_user("staff@example.com", "staff-password")
        listing = client.get("/v1/contact-messages").json()
        self.assertEqual(listing["total"], 1)
        message_id = listing["items"][0]["id"]
        self.assertEqual(listing["items"][0]["status"], "new")
        self.assertEqual(client.patch(f"/v1/contact-messages/{message_id}", {"status": "handled"}, format="json").status_code, 200)
        self.assertEqual(client.get("/v1/contact-messages", {"status": "new"}).json()["total"], 0)
        self.assertEqual(client.delete(f"/v1/contact-messages/{message_id}").status_code, 204)
        self.assertFalse(ContactMessage.objects.exists())


class LeadTests(ApiTestCase):
    cargo = {
        "name": "Ade Bello", "whatsapp": "+234 803 123 4567", "email": "ade@example.com", "direction": "pl_ng",
        "goodsType": "food", "description": "Spices", "weightKg": 12.5, "destinationCity": "Kraków", "notes": "", "locale": "en",
    }
    application = {
        "role": "courier", "name": "Jan", "email": "jan@example.com", "phone": "+48 600 100 200", "city": "Łódź",
        "hasLicence": True, "workStatus": "student", "availability": "weekends", "message": "", "locale": "pl",
    }

    def test_cargo_quotes(self):
        response = self.client.post("/v1/cargo-quotes", self.cargo, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertRegex(response.json()["reference"], r"^FC-[2-9A-HJ-NP-Z]{6}$")
        self.assertEqual(CargoQuote.objects.get().destination_city, "", "only shipments to Poland keep a city")
        self.assertEqual(len(mail.outbox), 0, "the website emails the team itself")

        bad = {**self.cargo, "whatsapp": "call me", "direction": "", "goodsType": "cars", "weightKg": "heavy", "description": "x" * 1001}
        self.assertEqual(
            self.client.post("/v1/cargo-quotes", bad, format="json").json(),
            {"errors": {"whatsapp": "phone", "direction": "required", "goodsType": "required", "description": "tooLong", "weightKg": "number"}},
        )

        client = self.as_user("staff@example.com", "staff-password")
        listing = client.get("/v1/cargo-quotes").json()
        self.assertEqual((listing["total"], listing["items"][0]["weightKg"], listing["items"][0]["status"]), (1, 12.5, "new"))
        quote_id = listing["items"][0]["id"]
        self.assertEqual(client.patch(f"/v1/cargo-quotes/{quote_id}", {"status": "in_progress"}, format="json").status_code, 200)
        self.assertEqual(client.get("/v1/cargo-quotes", {"status": "in_progress"}).json()["total"], 1)
        self.assertEqual(client.patch(f"/v1/cargo-quotes/{quote_id}", {"status": "handled"}, format="json").status_code, 422)
        self.assertEqual(client.delete(f"/v1/cargo-quotes/{quote_id}").status_code, 204)
        self.assertEqual(self.client.get("/v1/cargo-quotes").status_code, 401)

    def test_job_applications(self):
        response = self.client.post("/v1/job-applications", self.application, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(set(response.json()), {"id"})

        bad = {**self.application, "role": "pilot", "hasLicence": "yes", "city": "", "workStatus": None}
        self.assertEqual(
            self.client.post("/v1/job-applications", bad, format="json").json(),
            {"errors": {"role": "required", "city": "required", "hasLicence": "required", "workStatus": "required"}},
        )

        client = self.as_user("staff@example.com", "staff-password")
        item = client.get("/v1/job-applications").json()["items"][0]
        self.assertEqual((item["hasLicence"], item["workStatus"], item["city"]), (True, "student", "Łódź"))
        self.assertEqual(client.patch(f"/v1/job-applications/{item['id']}", {"status": "closed"}, format="json").json()["status"], "closed")
        self.assertEqual(client.delete(f"/v1/job-applications/{item['id']}").status_code, 204)
        self.assertFalse(JobApplication.objects.exists())

    def test_rate_limited_per_visitor(self):
        from rest_framework.throttling import SimpleRateThrottle

        with mock.patch.object(SimpleRateThrottle, "THROTTLE_RATES", {"enquiries": "1/hour"}):
            codes = [
                self.client.post("/v1/cargo-quotes", self.cargo, format="json", HTTP_X_API_KEY="secret", HTTP_X_VISITOR_IP=ip).status_code
                for ip in ("1.1.1.1", "1.1.1.1", "2.2.2.2")
            ]
        self.assertEqual(codes, [201, 429, 201])


class ContentTests(ApiTestCase):
    def test_services_crud_and_visibility(self):
        client = self.as_user("staff@example.com", "staff-password")
        response = client.post("/v1/services", service_payload(), format="json")
        self.assertEqual(response.status_code, 201, response.content)
        service = response.json()
        self.assertEqual(service["content"]["en"], "<p>Body </p>", "rich text is sanitised")
        self.assertEqual((service["brand"], service["comingSoon"]), ("cargo", False))

        self.assertEqual(client.post("/v1/services", service_payload(), format="json").json(), {"errors": {"slug": "taken"}})

        hidden = client.post("/v1/services", service_payload(slug="hidden", published=False, sortOrder=0), format="json").json()
        self.assertEqual([s["slug"] for s in self.client.get("/v1/services").json()], ["van-cargo"])
        self.assertEqual([s["slug"] for s in client.get("/v1/services?includeUnpublished=true").json()], ["hidden", "van-cargo"])
        self.assertEqual(self.client.get("/v1/services?includeUnpublished=true").status_code, 401)
        self.assertEqual(self.client.get(f"/v1/services/{hidden['id']}").status_code, 401)

        response = client.put(f"/v1/services/{hidden['id']}", service_payload(slug="hidden", title={"pl": "A", "en": "B"}), format="json")
        self.assertEqual(response.json()["title"], {"pl": "A", "en": "B"})
        self.assertEqual(client.put(f"/v1/services/{hidden['id']}", service_payload(), format="json").json(), {"errors": {"slug": "taken"}})

        errors = client.post("/v1/services", service_payload(slug="Bad Slug", title={"pl": ""}, content={"pl": "<p></p>", "en": "x"}, image="ftp://x", brand="taxi"), format="json").json()["errors"]
        self.assertEqual(errors, {"brand": "invalid", "slug": "invalid", "title.pl": "required", "title.en": "required", "content.pl": "required", "image": "invalid"})

        self.assertEqual(client.delete(f"/v1/services/{hidden['id']}").status_code, 204)
        self.assertEqual(Service.objects.count(), 1)

    def test_fleet(self):
        client = self.as_user()
        car = {
            "name": "Toyota Prius III", "year": 2011, "pricePerWeek": 600, "image": "", "color": "#C8102E",
            "fuel": {"pl": "Hybryda", "en": "Hybrid"}, "summary": {"pl": "Opis", "en": "Summary"},
            "features": {"pl": ["A", " "], "en": ["B"]}, "published": True, "sortOrder": 1,
        }
        response = client.post("/v1/fleet", car, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual((response.json()["color"], response.json()["features"]["pl"]), ("#c8102e", ["A"]))
        self.assertEqual(len(self.client.get("/v1/fleet").json()), 1)
        errors = client.post("/v1/fleet", {**car, "year": 1800, "color": "red", "features": {"pl": ["x"] * 13, "en": "x"}}, format="json").json()["errors"]
        self.assertEqual(errors, {"year": "invalid", "color": "invalid", "features.pl": "tooLong", "features.en": "invalid"})
        self.assertEqual(FleetCar.objects.count(), 1)

    def test_faqs(self):
        client = self.as_user("staff@example.com", "staff-password")
        faq = {
            "category": "cargo", "question": {"pl": "Pytanie?", "en": "Question?"},
            "answer": {"pl": "<p>Tak</p>", "en": "<p>Yes</p>"}, "published": True, "sortOrder": 2,
        }
        first = client.post("/v1/faqs", faq, format="json")
        self.assertEqual(first.status_code, 201, first.content)
        client.post("/v1/faqs", {**faq, "sortOrder": 1, "question": {"pl": "A?", "en": "A?"}}, format="json")
        client.post("/v1/faqs", {**faq, "published": False}, format="json")
        self.assertEqual([f["question"]["en"] for f in self.client.get("/v1/faqs").json()], ["A?", "Question?"])
        self.assertEqual(len(client.get("/v1/faqs?includeUnpublished=true").json()), 3)

        faq_id = first.json()["id"]
        updated = client.put(f"/v1/faqs/{faq_id}", {**faq, "category": "support"}, format="json").json()
        self.assertEqual(updated["category"], "support")
        errors = client.post("/v1/faqs", {**faq, "category": "drivers", "answer": {"pl": "", "en": "<p>x</p>"}}, format="json").json()
        self.assertEqual(errors, {"errors": {"category": "invalid", "answer.pl": "required"}})
        self.assertEqual(client.delete(f"/v1/faqs/{faq_id}").status_code, 204)
        self.assertEqual(Faq.objects.count(), 2)

    def test_settings(self):
        self.assertEqual(
            self.client.get("/v1/settings").json(),
            {"cargoRatePerKg": 50.0, "cargoMinWeightKg": 1.0, "cargoEstimatorEnabled": True},
        )
        body = {"cargoRatePerKg": 47.5, "cargoMinWeightKg": 2, "cargoEstimatorEnabled": False}
        self.assertEqual(self.client.put("/v1/settings", body, format="json").status_code, 401)
        client = self.as_user("staff@example.com", "staff-password")
        self.assertEqual(client.put("/v1/settings", body, format="json").json(), {**body, "cargoMinWeightKg": 2.0})
        self.assertEqual(self.client.get("/v1/settings").json()["cargoRatePerKg"], 47.5)
        bad = client.put("/v1/settings", {"cargoRatePerKg": -1, "cargoMinWeightKg": "x"}, format="json").json()
        self.assertEqual(bad, {"errors": {"cargoRatePerKg": "invalid", "cargoMinWeightKg": "invalid", "cargoEstimatorEnabled": "invalid"}})
        self.assertEqual(SiteSettings.objects.count(), 1)

    @override_settings(MEDIA_ROOT=TEMP_MEDIA, PUBLIC_BASE_URL="https://api.example.com")
    def test_uploads(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        client = self.as_user("staff@example.com", "staff-password")
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        response = client.post("/v1/uploads", {"file": SimpleUploadedFile("a.png", png, "image/png")}, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertRegex(response.json()["url"], r"^https://api\.example\.com/media/uploads/\d{4}/\d{2}/[0-9a-f]{32}\.png$")

        fake = SimpleUploadedFile("a.png", b"<script>alert(1)</script>", "image/png")
        self.assertEqual(client.post("/v1/uploads", {"file": fake}, format="multipart").json(), {"errors": {"file": "invalid"}})
        big = SimpleUploadedFile("a.png", png + b"\x00" * (4 * 1024 * 1024), "image/png")
        self.assertEqual(client.post("/v1/uploads", {"file": big}, format="multipart").status_code, 413)
        self.assertEqual(self.client.post("/v1/uploads", {}, format="multipart").status_code, 401)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()


class UserTests(ApiTestCase):
    def test_staff_cannot_manage_users(self):
        self.assertEqual(self.as_user("staff@example.com", "staff-password").get("/v1/users").status_code, 403)

    def test_manage_users(self):
        client = self.as_user()
        self.assertEqual([u["email"] for u in client.get("/v1/users").json()], ["admin@example.com", "staff@example.com"])

        new = {"email": "New@Example.com", "name": "New", "role": "staff", "password": "long-enough-1"}
        response = client.post("/v1/users", new, format="json")
        self.assertEqual(response.status_code, 201)
        user = response.json()
        self.assertEqual((user["email"], user["lastLoginAt"]), ("new@example.com", None))
        self.assertEqual(client.post("/v1/users", new, format="json").json(), {"errors": {"email": "taken"}})
        self.assertEqual(client.post("/v1/users", {**new, "email": "b@example.com", "password": "short"}, format="json").json(), {"errors": {"password": "tooShort"}})

        response = client.patch(f"/v1/users/{user['id']}", {"email": "new@example.com", "name": "Renamed", "role": "admin", "password": "another-password"}, format="json")
        self.assertEqual((response.json()["name"], response.json()["role"]), ("Renamed", "admin"))
        self.login("new@example.com", "another-password")

        self.assertEqual(client.patch(f"/v1/users/{self.admin.id}", {"email": "admin@example.com", "name": "A", "role": "staff"}, format="json").json(), {"errors": {"role": "ownRole"}})
        self.assertEqual(client.delete(f"/v1/users/{self.admin.id}").json(), {"errors": {"id": "self"}})
        self.assertEqual(client.delete(f"/v1/users/{user['id']}").status_code, 204)
        self.assertEqual(client.get(f"/v1/users/{user['id']}").status_code, 404)


class SeedTests(TestCase):
    def test_seed_content_is_idempotent(self):
        from django.core.management import call_command

        call_command("seed_content", stdout=mock.MagicMock())
        call_command("seed_content", stdout=mock.MagicMock())
        self.assertEqual((Service.objects.count(), FleetCar.objects.count(), Faq.objects.count()), (7, 3, 66))
        self.assertEqual(Service.objects.filter(brand="cargo", coming_soon=True).count(), 2)
        self.assertEqual(float(SiteSettings.load().cargo_rate_per_kg), 50.0)
