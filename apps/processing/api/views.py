from rest_framework import mixins, viewsets

from apps.processing import selectors
from apps.processing.api.serializers import ProcessingJobSerializer
from apps.processing.models import ProcessingJob


class ProcessingJobViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    # GenericViewSet + mixins: somente leitura (list e retrieve). Quem escreve no job é o
    # worker. Equivale ao ReadOnlyModelViewSet do DRF; os mixins explícitos deixam claro o que
    # o recurso oferece.
    serializer_class = ProcessingJobSerializer
    # Filtro simples por igualdade, sem FilterSet: ?status=failed&video=12
    filterset_fields = ["status", "video"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        # swagger_fake_view: na geração do OpenAPI o usuário é anônimo; devolve um queryset
        # vazio só para o drf-spectacular descobrir o model.
        if getattr(self, "swagger_fake_view", False):
            return ProcessingJob.objects.none()
        return selectors.job_queryset(user=self.request.user)
