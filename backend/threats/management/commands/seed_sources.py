"""Seed a few example sources so the dashboard has something to poll.

Usage: python manage.py seed_sources
"""
from django.core.management.base import BaseCommand

from threats.models import Source, SourceType


SAMPLE_SOURCES = [
    {
        "name": "IDF Press (RSS example)",
        "source_type": SourceType.RSS,
        "identifier": "https://www.idf.il/en/rss/",
    },
    {
        "name": "Gov.il News (RSS example)",
        "source_type": SourceType.RSS,
        "identifier": "https://www.gov.il/he/api/rss",
    },
    {
        "name": "Example Telegram OSINT channel",
        "source_type": SourceType.TELEGRAM,
        "identifier": "@example_osint_channel",
    },
    {
        "name": "Example X handle",
        "source_type": SourceType.X,
        "identifier": "example_handle",
    },
]


class Command(BaseCommand):
    help = "Create example monitoring sources for development/testing."

    def handle(self, *args, **options):
        created = 0
        for spec in SAMPLE_SOURCES:
            obj, was_created = Source.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "source_type": spec["source_type"],
                    "identifier": spec["identifier"],
                    "is_active": True,
                },
            )
            created += int(was_created)
            status = "created" if was_created else "exists"
            self.stdout.write(f"  [{status}] {obj.name}")
        self.stdout.write(self.style.SUCCESS(f"Done. {created} new source(s)."))
