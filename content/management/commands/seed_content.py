import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from content import serializers as s
from content.models import Article, FleetCar, Service

SEED_FILE = Path(settings.BASE_DIR) / "seed" / "content.json"


class Command(BaseCommand):
    help = "Adds the website's starting services, rental cars and articles (from seed/content.json)."

    def add_arguments(self, parser):
        parser.add_argument("--update", action="store_true", help="Overwrite items that already exist.")

    @transaction.atomic
    def handle(self, *args, update=False, **options):
        data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
        groups = [
            ("services", Service, s.validate_service, "slug", "slug"),
            ("fleet", FleetCar, s.validate_car, "name", "name"),
            ("articles", Article, s.validate_article, "slug", "slug"),
        ]
        for key, model, validate, lookup, source in groups:
            created = updated = 0
            for raw in data[key]:
                existing = model.objects.filter(**{lookup: raw[source]}).first()
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
