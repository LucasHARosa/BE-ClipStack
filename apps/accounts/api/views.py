from django.db.models import Count
from rest_framework import generics, mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts import services
from apps.accounts.api.serializers import (
    AdminUserSerializer,
    LoginSerializer,
    MeSerializer,
    RegisterSerializer,
    SetRoleSerializer,
)
from apps.accounts.models import User
from apps.core.permissions import IsAdminRole


class LoginView(TokenObtainPairView):
    # View do simplejwt com serializer próprio (claims extras) e throttle próprio:
    # throttle_classes substitui (não soma) os throttles padrão; o scope "login" limita
    # tentativas de senha por IP, contra força bruta.
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RegisterView(generics.CreateAPIView):
    # Generic View: endpoint isolado de um recurso (só "criar usuário"), sem lista nem detalhe.
    # CreateAPIView = CreateModelMixin + GenericAPIView: is_valid() → serializer.save() → 201.
    serializer_class = RegisterSerializer
    # Sobrescreve o padrão global (IsAuthenticated): quem se cadastra ainda não tem conta.
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    # Generic View: o recurso é sempre "o usuário logado", então não há {id} na URL.
    serializer_class = MeSerializer
    # Sem PUT: o perfil só aceita alteração parcial.
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        # get_object() devolve o próprio request.user em vez de buscar por pk na URL.
        return self.request.user


class AdminUserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    # GenericViewSet + mixins: recurso com CRUD PARCIAL (só listar e ver). Criar usuário é
    # o cadastro; apagar não existe (usuário é desativado).
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        # annotate: videos_count calculado no mesmo SELECT (reverso "videos").
        return User.objects.annotate(videos_count=Count("videos")).order_by("email")

    def get_serializer_class(self):
        # get_serializer_class(): serializer diferente por ação.
        if self.action == "set_role":
            return SetRoleSerializer
        return super().get_serializer_class()

    # @action(detail=True): rota extra sobre UM objeto → POST /admin/users/{id}/set-role/.
    @action(detail=True, methods=["post"], url_path="set-role")
    def set_role(self, request, pk=None):
        user = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.set_user_role(
            user=user, role=serializer.validated_data["role"], actor=request.user
        )
        user.videos_count = user.videos.count()
        return Response(AdminUserSerializer(user, context=self.get_serializer_context()).data)
