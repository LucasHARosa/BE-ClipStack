"""Rotas da versão 1 da API (/api/v1/).

Versionamento pela URL: uma mudança incompatível vira /api/v2/ sem quebrar quem usa a v1.
ViewSets → um DefaultRouter central (ele também gera a página raiz /api/v1/ listando os
recursos). O resto (Generic Views, APIView, FBV, rotas aninhadas) → path() em cada app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.api.views import AdminUserViewSet
from apps.notifications.api.views import NotificationViewSet
from apps.processing.api.views import ProcessingJobViewSet
from apps.videos.api.views import TagViewSet, VideoViewSet

router = DefaultRouter()
# basename: obrigatório quando o ViewSet não tem o atributo queryset (só get_queryset()).
# Ele define o nome das rotas: video-list, video-detail...
router.register("videos", VideoViewSet, basename="video")
router.register("tags", TagViewSet, basename="tag")
router.register("jobs", ProcessingJobViewSet, basename="job")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("admin/users", AdminUserViewSet, basename="admin-user")

urlpatterns = [
    path("", include("apps.accounts.api.urls")),
    path("", include("apps.videos.api.urls")),
    *router.urls,
]
