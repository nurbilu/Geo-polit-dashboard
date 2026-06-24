"""
Idempotently create the `nurADMIN` superuser.

The password is read from the NURADMIN_PASSWORD env var when present, otherwise
a default development password is used. Existing users are never overwritten
unless --force is passed (which only resets the password / elevates flags).

Usage:
    python manage.py seed_admin
    python manage.py seed_admin --force
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

ADMIN_USERNAME = "nurADMIN"
DEFAULT_PASSWORD = "Nur@Admin2026!"
DEFAULT_EMAIL = "nuradmin@geo-polit-dashboard.local"


class Command(BaseCommand):
    help = "Create the nurADMIN superuser if it does not already exist."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reset password and re-assert superuser flags if user exists.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        password = os.environ.get("NURADMIN_PASSWORD", DEFAULT_PASSWORD)
        email = os.environ.get("NURADMIN_EMAIL", DEFAULT_EMAIL)

        user = User.objects.filter(username=ADMIN_USERNAME).first()

        if user is None:
            User.objects.create_superuser(
                username=ADMIN_USERNAME, email=email, password=password
            )
            self.stdout.write(self.style.SUCCESS(
                f"Created superuser '{ADMIN_USERNAME}'."
            ))
            self._password_hint(password)
            return

        if options["force"]:
            user.email = email
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"Updated existing superuser '{ADMIN_USERNAME}' (--force)."
            ))
            self._password_hint(password)
        else:
            self.stdout.write(self.style.WARNING(
                f"Superuser '{ADMIN_USERNAME}' already exists; left untouched. "
                f"Use --force to reset the password."
            ))

    def _password_hint(self, password: str) -> None:
        if "NURADMIN_PASSWORD" in os.environ:
            self.stdout.write("  Password: (from NURADMIN_PASSWORD env var)")
        else:
            self.stdout.write(self.style.WARNING(
                f"  Password (default, change in production): {password}"
            ))
