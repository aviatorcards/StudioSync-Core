"""
Management command to populate the database with sample/demo data.
Creates an admin, a studio, 5 teachers, and 20 students.

Usage:
    docker compose run backend python manage.py create_sample_data
    docker compose run backend python manage.py create_sample_data --reset
"""

import random

from django.core.management.base import BaseCommand
from django.utils import timezone

FIRST_NAMES = [
    "James",
    "Mary",
    "Robert",
    "Patricia",
    "John",
    "Jennifer",
    "Michael",
    "Linda",
    "William",
    "Elizabeth",
    "David",
    "Barbara",
    "Richard",
    "Susan",
    "Joseph",
    "Jessica",
    "Thomas",
    "Sarah",
    "Charles",
    "Karen",
]
LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
]
INSTRUMENTS = ["Piano", "Guitar", "Violin", "Drums", "Vocal", "Saxophone", "Flute", "Cello"]


class Command(BaseCommand):
    help = "Populate the database with sample data (studio, teachers, students)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing sample data before creating fresh data",
        )

    def handle(self, *args, **options):
        from studiosync_core.core.models import Student, Studio, Teacher, User

        if options["reset"]:
            self.stdout.write("🗑️  Deleting existing sample data...")
            User.objects.filter(email__endswith="@test.com").delete()
            Studio.objects.filter(name="StudioSync Academy").delete()
            self.stdout.write(self.style.SUCCESS("   Done."))

        self.stdout.write("🌱 Creating sample data...")

        # Admin
        admin, created = User.objects.get_or_create(
            email="admin@test.com",
            defaults={
                "first_name": "Admin",
                "last_name": "User",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        if created:
            admin.set_password("admin123")
            admin.save()
            self.stdout.write(self.style.SUCCESS("  ✅ Admin created: admin@test.com / admin123"))
        else:
            self.stdout.write("  ℹ️  Admin already exists: admin@test.com")

        # Studio
        studio, created = Studio.objects.get_or_create(
            name="StudioSync Academy",
            owner=admin,
            defaults={
                "email": "contact@studiosync.com",
                "address_line1": "123 Music Lane",
                "city": "Nashville",
                "state": "TN",
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"  ✅ Studio created: {studio.name}"))
        else:
            self.stdout.write(f"  ℹ️  Studio already exists: {studio.name}")

        # Teachers
        teachers = []
        for i in range(5):
            email = f"teacher{i + 1}@test.com"
            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": random.choice(FIRST_NAMES),
                    "last_name": random.choice(LAST_NAMES),
                    "role": "teacher",
                    "is_active": True,
                },
            )
            if user_created:
                user.set_password("teacher123")
                user.save()

            instrument = random.choice(INSTRUMENTS)
            teacher, _ = Teacher.objects.get_or_create(
                user=user,
                defaults={
                    "studio": studio,
                    "bio": f"Experienced {instrument} instructor.",
                    "instruments": [instrument],
                    "hourly_rate": random.randint(40, 80),
                },
            )
            teachers.append(teacher)

        self.stdout.write(
            self.style.SUCCESS(
                "  ✅ 5 teachers created (teacher1@test.com … teacher5@test.com / teacher123)"
            )
        )

        # Students
        for i in range(1, 21):
            email = f"student{i}@test.com"
            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": random.choice(FIRST_NAMES),
                    "last_name": random.choice(LAST_NAMES),
                    "role": "student",
                    "is_active": True,
                },
            )
            if user_created:
                user.set_password("student123")
                user.save()

            Student.objects.get_or_create(
                user=user,
                defaults={
                    "studio": studio,
                    "instrument": random.choice(INSTRUMENTS),
                    "primary_teacher": random.choice(teachers),
                    "enrollment_date": timezone.now().date(),
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "  ✅ 20 students created (student1@test.com … student20@test.com / student123)"
            )
        )
        self.stdout.write(self.style.SUCCESS("\n🎉 Sample data created successfully!"))
