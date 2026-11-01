from rest_framework import mixins, viewsets

from apps.processing import selectors
from apps.processing.api.serializers import ProcessingJobSerializer


class ProcessingJobViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    # GenericViewSet + mixins: somente leitura (list e retrieve). Quem escreve no job é o
    # worker. Equivale ao ReadOnlyModelViewSet do DRF; os mixins explícitos deixam claro o que
    # o recurso oferece.
    serializer_class = ProcessingJobSerializer

    def get_queryset(self):
        return selectors.job_queryset(user=self.request.user)
