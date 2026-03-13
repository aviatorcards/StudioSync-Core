"""
Tests for the create_sample_data management command.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from studiosync_core.core.models import Student, Studio, Teacher, User

ADMIN_EMAIL = "admin@test.com"
STUDIO_NAME = "StudioSync Academy"


class CreateSampleDataCommandTests(TestCase):
    def test_command_creates_admin_user(self):
        out = StringIO()
        call_command("create_sample_data", stdout=out)
        self.assertTrue(User.objects.filter(email=ADMIN_EMAIL, role="admin").exists())

    def test_command_creates_studio(self):
        call_command("create_sample_data", stdout=StringIO())
        self.assertTrue(Studio.objects.filter(name=STUDIO_NAME).exists())

    def test_command_creates_five_teachers(self):
        call_command("create_sample_data", stdout=StringIO())
        self.assertEqual(Teacher.objects.count(), 5)

    def test_command_creates_twenty_students(self):
        call_command("create_sample_data", stdout=StringIO())
        self.assertEqual(Student.objects.count(), 20)

    def test_command_is_idempotent(self):
        """Running the command twice should not duplicate data."""
        call_command("create_sample_data", stdout=StringIO())
        call_command("create_sample_data", stdout=StringIO())
        self.assertEqual(User.objects.filter(email=ADMIN_EMAIL).count(), 1)
        self.assertEqual(Studio.objects.filter(name=STUDIO_NAME).count(), 1)
        self.assertEqual(Teacher.objects.count(), 5)
        self.assertEqual(Student.objects.count(), 20)

    def test_reset_flag_clears_existing_data(self):
        """--reset should wipe sample data before recreating."""
        call_command("create_sample_data", stdout=StringIO())
        call_command("create_sample_data", "--reset", stdout=StringIO())
        # Counts should still be the same after reset + recreate
        self.assertEqual(Teacher.objects.count(), 5)
        self.assertEqual(Student.objects.count(), 20)

    def test_command_output_mentions_success(self):
        out = StringIO()
        call_command("create_sample_data", stdout=out)
        output = out.getvalue()
        self.assertIn("Sample data created successfully", output)
