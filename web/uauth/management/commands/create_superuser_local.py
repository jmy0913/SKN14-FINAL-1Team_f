import os
from dotenv import load_dotenv
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

load_dotenv()

SUPERUSER_PASSWORD = os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin123")


class Command(BaseCommand):
    help = "Create a superuser if not already exists"

    def handle(self, *args, **options):
        User = get_user_model()
        if not User.objects.filter(id="admin2").exists():
            User.objects.create_superuser(
                id="admin2",
                email="admin2@example.com",
                password=SUPERUSER_PASSWORD,
                name="Admin User",
                phone="123-4567-8900",
                gender="male",
                birthday="2000-01-01",
                rank="cto",
            )
            self.stdout.write(self.style.SUCCESS("Superuser created successfully"))
        else:
            self.stdout.write(self.style.SUCCESS("Superuser already exists"))
