from rest_framework import mixins, viewsets

from apps.processing import selectors
from apps.processing.api.serializers import ProcessingJobSerializer
from apps.processing.models import ProcessingJob


class ProcessingJobViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = ProcessingJobSerializer
    filterset_fields = ["status", "video"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        # Na geração do OpenAPI o usuário é anônimo.
        if getattr(self, "swagger_fake_view", False):
            return ProcessingJob.objects.none()
        return selectors.job_queryset(user=self.request.user)
