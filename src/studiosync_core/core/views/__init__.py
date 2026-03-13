# Expose modules for direct access
from . import backup, core, gdpr, setup, stats  # noqa: F401
from .backup import export_system, import_system  # noqa: F401
from .core import (  # noqa: F401
    BandViewSet,
    ReportsExportView,
    StudentViewSet,
    StudioViewSet,
    TeacherViewSet,
    UserViewSet,
)
from .gdpr import (  # noqa: F401
    export_my_data,
    privacy_dashboard,
    record_consent,
    request_account_deletion,
    update_privacy_settings,
)
from .health import health_check, readiness_check  # noqa: F401
from .setup import check_setup_status, complete_setup_wizard  # noqa: F401
from .stats import DashboardAnalyticsView, DashboardStatsView  # noqa: F401
