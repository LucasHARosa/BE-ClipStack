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
    # Substitui (não soma) os throttles padrão: limita tentativas de senha por IP.
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


class AdminUserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    # Sem create/destroy: criar é o cadastro, e usuário é desativado, não apagado.
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return User.objects.annotate(videos_count=Count("videos")).order_by("email")

    @action(detail=True, methods=["post"], url_path="set-role", serializer_class=SetRoleSerializer)
    def set_role(self, request, pk=None):
        user = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.set_user_role(
            user=user, role=serializer.validated_data["role"], actor=request.user
        )
        user.videos_count = user.videos.count()
        return Response(AdminUserSerializer(user, context=self.get_serializer_context()).data)
