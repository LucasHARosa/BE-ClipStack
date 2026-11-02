from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.idempotency import run_idempotent
from apps.core.permissions import IsAdminRole, IsAuthorOrAdmin, IsOwnerOrReadOnly
from apps.videos import selectors, services
from apps.videos.api.serializers import (
    CommentSerializer,
    DashboardStatsSerializer,
    TagSerializer,
    VideoDetailSerializer,
    VideoListSerializer,
    VideoUpdateSerializer,
    VideoUploadSerializer,
)
from apps.videos.filters import VideoFilter
from apps.videos.models import Comment, Tag, Video


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def meta_view(request):
    # O frontend não duplica as choices em TypeScript.
    return Response(
        {
            "video_statuses": [{"value": v, "label": label} for v, label in Video.Status.choices],
            "visibilities": [{"value": v, "label": label} for v, label in Video.Visibility.choices],
            "upload": {
                "allowed_extensions": settings.VIDEO_ALLOWED_EXTENSIONS,
                "max_size_mb": settings.VIDEO_MAX_UPLOAD_SIZE_MB,
            },
        }
    )


class DashboardStatsView(APIView):
    @extend_schema(responses=DashboardStatsSerializer)
    def get(self, request):
        return Response(selectors.dashboard_stats(user=request.user))


class VideoViewSet(viewsets.ModelViewSet):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_class = VideoFilter
    search_fields = ["title"]
    ordering_fields = ["created_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Prefetch só do que a ação serializa: o destroy não serializa e a lista não tem jobs.
        if self.action == "destroy":
            return Video.objects.visible_to(self.request.user)
        return selectors.visible_videos(user=self.request.user, with_jobs=self.action != "list")

    def get_permissions(self):
        # Editar: só o dono. Apagar: o dono ou o admin (moderação).
        if self.action in {"update", "partial_update"}:
            return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), (IsOwnerOrReadOnly | IsAdminRole)()]
        return super().get_permissions()

    def get_throttles(self):
        # Soma o scope "upload" aos limites padrão.
        if self.action == "create":
            self.throttle_scope = "upload"
            return [*super().get_throttles(), ScopedRateThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action == "create":
            return VideoUploadSerializer
        if self.action in {"update", "partial_update"}:
            return VideoUpdateSerializer
        if self.action == "list":
            return VideoListSerializer
        return VideoDetailSerializer

    @extend_schema(
        request={"multipart/form-data": VideoUploadSerializer},
        responses={201: VideoDetailSerializer},
        parameters=[
            OpenApiParameter(
                "Idempotency-Key",
                OpenApiTypes.STR,
                OpenApiParameter.HEADER,
                description="Chave única por operação; repetir devolve a resposta original.",
            )
        ],
    )
    def create(self, request, *args, **kwargs):
        return run_idempotent(request, lambda: self._create_video(request))

    def _create_video(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        video = services.create_video(owner=request.user, **serializer.validated_data)
        output = VideoDetailSerializer(video, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=VideoUpdateSerializer, responses=VideoDetailSerializer)
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        video = self.get_object()
        serializer = self.get_serializer(video, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        video = services.update_video(video=video, data=dict(serializer.validated_data))
        output = VideoDetailSerializer(video, context=self.get_serializer_context())
        return Response(output.data)

    def perform_destroy(self, instance):
        # Soft delete em vez do DELETE.
        services.delete_video(video=instance, actor=self.request.user)

    @extend_schema(request=None, responses={202: VideoDetailSerializer})
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsOwnerOrReadOnly],
    )
    def reprocess(self, request, pk=None):
        video = self.get_object()
        services.reprocess_video(video_id=video.pk)
        video = self.get_queryset().get(pk=video.pk)
        output = VideoDetailSerializer(video, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_202_ACCEPTED)


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    # Lista curta, usada inteira pelo frontend.
    pagination_class = None

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.IsAuthenticated()]
        return [IsAdminRole()]


class CommentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CommentSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), IsAuthorOrAdmin()]
        return super().get_permissions()

    def get_parent_video(self):
        # Vídeo invisível → 404, inclusive para comentar. Cacheado na view (1 query).
        if not hasattr(self, "_video"):
            self._video = get_object_or_404(
                Video.objects.visible_to(self.request.user), pk=self.kwargs["video_pk"]
            )
        return self._video

    def get_queryset(self):
        # Na geração do OpenAPI não há request real nem video_pk.
        if getattr(self, "swagger_fake_view", False):
            return Comment.objects.none()
        return self.get_parent_video().comments.select_related("author")

    def perform_create(self, serializer):
        serializer.save(video=self.get_parent_video(), author=self.request.user)
