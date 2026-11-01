from rest_framework import mixins, viewsets

from apps.processing.api.serializers import ProcessingJobSerializer
from apps.processing.models import ProcessingJob


class ProcessingJobViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    # GenericViewSet + mixins: somente leitura (list e retrieve). Quem escreve no job é o
    # worker. Equivale ao ReadOnlyModelViewSet do DRF; os mixins explícitos deixam claro o que
    # o recurso oferece.
    serializer_class = ProcessingJobSerializer

    def get_queryset(self):
        qs = ProcessingJob.objects.select_related("video")
        user = self.request.user
        if getattr(user, "is_admin", False):
            return qs
        # O usuário vê só os jobs dos próprios vídeos (que não foram apagados).
        return qs.filter(video__owner=user, video__is_deleted=False)
