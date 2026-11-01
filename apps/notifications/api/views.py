from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.pagination import NewestFirstCursorPagination
from apps.notifications import services
from apps.notifications.api.serializers import NotificationSerializer
from apps.notifications.models import Notification


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    # GenericViewSet + mixins: só list. Notificação não é criada pela API (o worker cria).
    serializer_class = NotificationSerializer
    # Feed que cresce o tempo todo: cursor em vez de número de página.
    pagination_class = NewestFirstCursorPagination
    # Sem filtros/ordenação do cliente: a CursorPagination define a ordem.
    filter_backends = []

    def get_queryset(self):
        # Só as próprias notificações. Sem exceção para admin: notificação é privada.
        return Notification.objects.filter(user=self.request.user)

    # @action(detail=False): rota extra na COLEÇÃO → POST /notifications/mark-all-read/.
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        updated = services.mark_all_read(user=request.user)
        return Response({"updated": updated})
