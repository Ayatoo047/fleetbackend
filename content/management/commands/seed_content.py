import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from content import serializers as s
from content.models import Faq, FleetCar, Service, SiteSettings

SEED_FILE = Path(settings.BASE_DIR) / "seed" / "content.json"


class Command(BaseCommand):
    help = "Adds the website's starting services, rental cars, FAQ and settings (from seed/content.json)."

    def add_arguments(self, parser):
        parser.add_argument("--update", action="store_true", help="Overwrite items and settings that already exist.")

    @transaction.atomic
    def handle(self, *args, update=False, **options):
        data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
        # Each item is matched to an existing one by a natural key, so running this twice adds nothing.
        groups = [
            ("services", Service, s.validate_service, lambda raw: {"slug": raw["slug"]}),
            ("fleet", FleetCar, s.validate_car, lambda raw: {"name": raw["name"]}),
            ("faqs", Faq, s.validate_faq, lambda raw: {"question__en": raw["question"]["en"]}),
        ]
        for key, model, validate, lookup in groups:
            created = updated = 0
            for raw in data[key]:
                existing = model.objects.filter(**lookup(raw)).first()
                if existing and not update:
                    continue
                fields = validate(raw, instance=existing)
                if existing:
                    for field, value in fields.items():
                        setattr(existing, field, value)
                    existing.save()
                    updated += 1
                else:
                    model.objects.create(**fields)
                    created += 1
            self.stdout.write(f"{key}: {created} created, {updated} updated")

        if update or not SiteSettings.objects.exists():
            s.save_settings(s.validate_settings(data["settings"]))
            self.stdout.write("settings: saved")
