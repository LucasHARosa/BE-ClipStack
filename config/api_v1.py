from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.api.views import AdminUserViewSet
from apps.core.health import health_view
from apps.notifications.api.views import NotificationViewSet
from apps.processing.api.views import ProcessingJobViewSet
from apps.videos.api.views import TagViewSet, VideoViewSet

router = DefaultRouter()
router.register("videos", VideoViewSet, basename="video")
router.register("tags", TagViewSet, basename="tag")
router.register("jobs", ProcessingJobViewSet, basename="job")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("admin/users", AdminUserViewSet, basename="admin-user")

urlpatterns = [
    path("health/", health_view, name="health"),
    path("", include("apps.accounts.api.urls")),
    path("", include("apps.videos.api.urls")),
    *router.urls,
]
