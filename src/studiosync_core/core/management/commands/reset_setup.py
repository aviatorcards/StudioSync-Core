"""
Management command to reset setup wizard status (development only)
"""

from django.core.management.base import BaseCommand

from studiosync_core.core.models import SetupStatus


class Command(BaseCommand):
    help = "Reset setup status (DANGER: Use only in development)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm reset action",
        )

    def handle(self, *args, **options):
        """Reset setup status"""
        if not options["confirm"]:
            self.stdout.write(
                self.style.ERROR("This will reset setup status. Use --confirm to proceed")
            )
            return

        deleted_count, _ = SetupStatus.objects.all().delete()

        if deleted_count > 0:
            self.stdout.write(self.style.SUCCESS("Setup status reset successfully"))
            self.stdout.write(f"Deleted {deleted_count} setup status record(s)")
        else:
            self.stdout.write(self.style.WARNING("No setup status records found"))

        self.stdout.write("You can now run the setup wizard again at: /setup")
