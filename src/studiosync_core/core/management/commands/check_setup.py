"""
Management command to check setup wizard status
"""

from django.core.management.base import BaseCommand

from studiosync_core.core.models import SetupStatus


class Command(BaseCommand):
    help = "Check if initial setup wizard has been completed"

    def handle(self, *args, **options):
        """Check and display setup status"""
        setup = SetupStatus.objects.first()

        if not setup:
            self.stdout.write(self.style.WARNING("Setup has not been started"))
            self.stdout.write("Run the setup wizard at: /setup")
            return

        if setup.is_completed:
            self.stdout.write(self.style.SUCCESS(f"Setup completed on {setup.completed_at}"))
            self.stdout.write(f"Version: {setup.setup_version}")

            # Display enabled features
            if setup.features_enabled:
                enabled_features = [
                    k.replace("_enabled", "") for k, v in setup.features_enabled.items() if v
                ]
                if enabled_features:
                    self.stdout.write(f'Enabled features: {", ".join(enabled_features)}')
        else:
            self.stdout.write(self.style.WARNING("Setup started but not completed"))
            self.stdout.write("Please complete the setup wizard at: /setup")
