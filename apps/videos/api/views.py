from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.idempotency import run_idempotent
from apps.videos import selectors, services
from apps.videos.api.serializers import (
    CommentSerializer,
    TagSerializer,
    VideoDetailSerializer,
    VideoListSerializer,
    VideoUpdateSerializer,
    VideoUploadSerializer,
)
from apps.videos.models import Tag, Video

# Permissões desta etapa: só autenticação (padrão global) e IsAdminUser na escrita de tags.
# A matriz completa (dono edita, admin modera, 404 x 403) entra na etapa 6.


# --------------------------------------------------------------------------- FBV


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def meta_view(request):
    # @api_view (FBV, Function-Based View): endpoint de leitura, sem recurso nem CRUD.
    # Dá ao frontend as opções válidas sem duplicar as choices em TypeScript.
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


# --------------------------------------------------------------------------- APIView


class DashboardStatsView(APIView):
    # APIView: não é um recurso com CRUD, é um relatório (agregações). Um método por verbo.
    def get(self, request):
        return Response(selectors.dashboard_stats(user=request.user))


# --------------------------------------------------------------------------- ModelViewSet


class VideoViewSet(viewsets.ModelViewSet):
    # ModelViewSet: recurso com CRUD COMPLETO (list, create, retrieve, update, destroy)
    # + @action reprocess. multipart para o upload do arquivo; JSON para o PATCH.
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        # get_queryset() decide o que cada usuário PODE VER. Fora dele → 404 em qualquer ação
        # de detalhe, sem revelar que o vídeo existe (vídeo privado de outra pessoa).
        # Prefetch só do que o serializer da ação vai ler: o destroy não serializa nada e a
        # lista não mostra o último job.
        if self.action == "destroy":
            return Video.objects.visible_to(self.request.user)
        return selectors.video_queryset(user=self.request.user, with_jobs=self.action != "list")

    def get_serializer_class(self):
        # Um serializer por ação: entrada e saída têm formatos diferentes.
        if self.action == "create":
            return VideoUploadSerializer
        if self.action in {"update", "partial_update"}:
            return VideoUpdateSerializer
        if self.action == "list":
            return VideoListSerializer
        return VideoDetailSerializer

    def create(self, request, *args, **kwargs):
        # Com o header Idempotency-Key, repetir o POST devolve a resposta original em vez de
        # criar outro vídeo (retry depois de timeout, clique duplo).
        return run_idempotent(request, lambda: self._create_video(request))

    def _create_video(self, request):
        # O serializer só valida; quem cria é o service. A resposta usa o serializer de
        # SAÍDA (detalhe), não o de entrada.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        video = services.create_video(owner=request.user, **serializer.validated_data)
        output = VideoDetailSerializer(video, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        video = self.get_object()
        serializer = self.get_serializer(video, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        video = services.update_video(video=video, data=dict(serializer.validated_data))
        output = VideoDetailSerializer(video, context=self.get_serializer_context())
        return Response(output.data)

    def perform_destroy(self, instance):
        # perform_destroy(): gancho do DestroyModelMixin. Troca o DELETE do banco pelo soft
        # delete do service; a resposta continua 204.
        services.delete_video(video=instance, actor=self.request.user)

    # @action(detail=True): POST /videos/{id}/reprocess/. A view só orquestra: get_object()
    # (visibilidade → 404), service (regra + lock → 409 se não puder) e resposta.
    @action(detail=True, methods=["post"])
    def reprocess(self, request, pk=None):
        video = self.get_object()
        services.reprocess_video(video_id=video.pk)
        video = self.get_queryset().get(pk=video.pk)
        output = VideoDetailSerializer(video, context=self.get_serializer_context())
        # 202 Accepted: o pedido foi aceito, mas o trabalho acontece depois, na fila.
        return Response(output.data, status=status.HTTP_202_ACCEPTED)


class TagViewSet(viewsets.ModelViewSet):
    # ModelViewSet: CRUD completo de tags; a leitura é para todos, a escrita só para admin.
    queryset = Tag.objects.all()
    serializer_class = TagSerializer

    def get_permissions(self):
        # get_permissions(): permissões diferentes por ação.
        if self.action in {"list", "retrieve"}:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]


# --------------------------------------------------------------------------- GenericViewSet


class CommentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    # GenericViewSet + mixins: CRUD PARCIAL. Comentário não tem update (nem retrieve isolado).
    # Rota aninhada /videos/{video_pk}/comments/, montada à mão em urls.py.
    serializer_class = CommentSerializer

    def get_video(self):
        # O vídeo precisa estar visível para o usuário; senão 404 (inclusive para comentar).
        if not hasattr(self, "_video"):
            self._video = get_object_or_404(
                Video.objects.visible_to(self.request.user), pk=self.kwargs["video_pk"]
            )
        return self._video

    def get_queryset(self):
        # Reverso video.comments + select_related do autor (evita N+1 no author_username).
        return self.get_video().comments.select_related("author")

    def perform_create(self, serializer):
        # CRUD simples, sem regra: serializer.save() aqui é idiomático. video e author vêm
        # do contexto (URL e request.user), nunca do corpo da requisição.
        serializer.save(video=self.get_video(), author=self.request.user)
