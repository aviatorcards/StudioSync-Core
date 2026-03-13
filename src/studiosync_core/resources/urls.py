from django.urls import include, path

from config.routers import OptionalSlashRouter

from .views import PublicResourceViewSet, ResourceFolderViewSet, ResourceViewSet, SetlistViewSet

router = OptionalSlashRouter()
router.register(r"library", ResourceViewSet, basename="resource")
router.register(r"folders", ResourceFolderViewSet, basename="resource-folder")
router.register(r"public", PublicResourceViewSet, basename="public-resource")
router.register(r"setlists", SetlistViewSet, basename="setlist")

urlpatterns = [
    path("", include(router.urls)),
]
