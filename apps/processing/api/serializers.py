from rest_framework import serializers

from apps.processing.models import ProcessingJob


class ProcessingJobSerializer(serializers.ModelSerializer):
    video_title = serializers.CharField(source="video.title", read_only=True)

    class Meta:
        model = ProcessingJob
        fields = (
            "id",
            "video",
            "video_title",
            "status",
            "progress",
            "attempts",
            "error_message",
            "created_at",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields
