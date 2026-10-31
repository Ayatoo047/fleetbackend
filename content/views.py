import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import Invalid
from core.utils import flag

from . import serializers as s
from .models import Faq, FleetCar, Service, SiteSettings


class ContentCollectionView(APIView):
    """
    `GET` lists published items for the website, or every item for a signed-in admin with
    `?includeUnpublished=true`. `POST` (admin) creates an item.
    """

    model = None
    to_json = None
    validate = None

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]

    def get(self, request):
        qs = self.model.objects.all()
        if flag(request, "includeUnpublished"):
            if not request.user.is_authenticated:
                raise NotAuthenticated()
        else:
            qs = qs.filter(published=True)
        return Response([type(self).to_json(item) for item in qs])

    def post(self, request):
        item = self.model.objects.create(**type(self).validate(request.data))
        return Response(type(self).to_json(item), status=status.HTTP_201_CREATED)


class ContentDetailView(APIView):
    """Admin-only `GET`, `PUT` (replace) and `DELETE` of one item."""

    model = None
    to_json = None
    validate = None

    def get_object(self, pk):
        item = self.model.objects.filter(pk=pk).first()
        if item is None:
            raise NotFound()
        return item

    def get(self, request, pk):
        return Response(type(self).to_json(self.get_object(pk)))

    def put(self, request, pk):
        item = self.get_object(pk)
        for field, value in type(self).validate(request.data, instance=item).items():
            setattr(item, field, value)
        item.save()
        return Response(type(self).to_json(item))

    def delete(self, request, pk):
        self.model.objects.filter(pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ServiceCollectionView(ContentCollectionView):
    model, to_json, validate = Service, s.service_to_json, s.validate_service


class ServiceDetailView(ContentDetailView):
    model, to_json, validate = Service, s.service_to_json, s.validate_service


class FleetCollectionView(ContentCollectionView):
    model, to_json, validate = FleetCar, s.car_to_json, s.validate_car


class FleetDetailView(ContentDetailView):
    model, to_json, validate = FleetCar, s.car_to_json, s.validate_car


class FaqCollectionView(ContentCollectionView):
    model, to_json, validate = Faq, s.faq_to_json, s.validate_faq


class FaqDetailView(ContentDetailView):
    model, to_json, validate = Faq, s.faq_to_json, s.validate_faq


class SettingsView(APIView):
    """`GET` (public) and `PUT` (staff) the site settings, such as the cargo estimator's rate."""

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]

    def get(self, request):
        return Response(s.settings_to_json(SiteSettings.load()))

    def put(self, request):
        return Response(s.settings_to_json(s.save_settings(s.validate_settings(request.data))))


MAX_IMAGE_BYTES = int(3.5 * 1024 * 1024)


def image_extension(head):
    """The file extension for JPEG, PNG, WebP, AVIF or GIF data, judged by its first bytes."""
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head[4:8] == b"ftyp" and head[8:12] in (b"avif", b"avis"):
        return ".avif"
    return None


class UploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get("file")
        if file is None or file.size == 0:
            raise Invalid({"file": "required"})
        if file.size > MAX_IMAGE_BYTES:
            return Response({"errors": {"file": "tooLarge"}}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        extension = image_extension(file.read(16))
        if extension is None:
            raise Invalid({"file": "invalid"})
        file.seek(0)

        name = default_storage.save(f"uploads/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{extension}", file)
        url = default_storage.url(name)
        if not url.startswith(("http://", "https://")):
            url = f"{settings.PUBLIC_BASE_URL}{url}" if settings.PUBLIC_BASE_URL else request.build_absolute_uri(url)
        return Response({"url": url}, status=status.HTTP_201_CREATED)
