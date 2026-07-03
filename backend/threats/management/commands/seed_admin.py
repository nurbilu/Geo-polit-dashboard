"""
Idempotently seed the initial superuser from environment variables.

Credentials are read strictly from the environment — no plaintext passwords
are stored in this file or the repository:

    ADMIN_USERNAME   (required)  the superuser's username
    ADMIN_PASSWORD   (required)  the superuser's password
    ADMIN_EMAIL      (optional)  defaults to <username>@localhost

Usage:
    python manage.py seed_admin
    python manage.py seed_admin --force   # reset password / re-assert flags
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create/refresh the initial superuser from ADMIN_* environment variables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reset the password and re-assert superuser flags if the user exists.",
        )

    def handle(self, *args, **options):
        username = os.getenv("ADMIN_USERNAME")
        password = os.getenv("ADMIN_PASSWORD")
        email = os.getenv("ADMIN_EMAIL", f"{username}@localhost" if username else "")

        if not username or not password:
            raise CommandError(
                "ADMIN_USERNAME and ADMIN_PASSWORD must be set in the environment "
                "(.env). Refusing to create a superuser without them."
            )

        User = get_user_model()
        user = User.objects.filter(username=username).first()

        if user is None:
            User.objects.create_superuser(
                username=username, email=email, password=password
            )
            self.stdout.write(self.style.SUCCESS(
                f"Created superuser '{username}' (credentials from environment)."
            ))
            return

        if options["force"]:
            user.email = email or user.email
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"Updated existing superuser '{username}' (--force)."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Superuser '{username}' already exists; left untouched. "
                f"Use --force to reset the password."
            ))
