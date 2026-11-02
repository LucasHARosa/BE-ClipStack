from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.pagination import NewestFirstCursorPagination
from apps.notifications import services
from apps.notifications.api.serializers import NotificationSerializer
from apps.notifications.models import Notification


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    pagination_class = NewestFirstCursorPagination
    # A CursorPagination define a ordem; o cliente não pode mudá-la.
    filter_backends = []

    def get_queryset(self):
        # Sem exceção para admin: notificação é privada.
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        updated = services.mark_all_read(user=request.user)
        return Response({"updated": updated})
