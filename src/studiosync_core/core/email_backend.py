from django.core.mail.backends.smtp import EmailBackend

from studiosync_core.core.models import User


class ParameterizedEmailBackend(EmailBackend):
    """
    An email backend that configures itself based on system-wide settings
    stored in the database (via the main Admin user's preferences) rather than
    settings.py.
    """

    def __init__(
        self,
        host=None,
        port=None,
        username=None,
        password=None,
        use_tls=None,
        fail_silently=False,
        **kwargs,
    ):

        print("=" * 60)
        print("ParameterizedEmailBackend initializing...")

        # Try to find the admin user's preferences to override settings
        # In a real multi-tenant system, this would need to resolve the tenant from thread locals
        try:
            # For this MVP, we pick the first admin found, or a specific system owner
            admin = User.objects.filter(role="admin").first()
            if admin and admin.preferences and "technical" in admin.preferences:
                tech_settings = admin.preferences["technical"]

                print("Found admin preferences for email")

                host = tech_settings.get("smtp_host") or host
                port = tech_settings.get("smtp_port") or port
                username = tech_settings.get("smtp_username") or username
                password = tech_settings.get("smtp_password") or password
                from_email = tech_settings.get(
                    "smtp_from_email"
                )  # Not used in backend init but good to note

                # Logic for TLS/SSL
                # If explicit TLS setting exists:
                if "smtp_use_tls" in tech_settings:
                    use_tls = tech_settings["smtp_use_tls"]

                # Heuristic fallback if direct boolean not clean
                if str(port) == "465":
                    kwargs["use_ssl"] = True
                    use_tls = False

                print("Email config from DB:")
                print(f"  Host: {host}")
                print(f"  Port: {port}")
                print(f"  Username: {username}")
                print(f"  Password: {'*' * len(password) if password else 'None'}")
                print(f"  Use TLS: {use_tls}")
                print(f"  Use SSL: {kwargs.get('use_ssl', False)}")
                print(f"  From Email: {from_email}")
            else:
                print("No admin preferences found, using defaults")
        except Exception as e:
            # Fallback to settings.py if DB is unreachable (e.g. during migrations)
            print(f"Error loading email config from DB: {e}")
            import traceback

            traceback.print_exc()

        print("Calling parent EmailBackend.__init__")
        super().__init__(
            host=host,
            port=port,
            username=username,
            password=password,
            use_tls=use_tls,
            fail_silently=fail_silently,
            **kwargs,
        )
        print("=" * 60)
