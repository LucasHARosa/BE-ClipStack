from pathlib import Path

from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.videos.models import Comment, Tag, Video, VideoMetadata


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name")


class VideoMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoMetadata
        fields = ("duration_seconds", "resolution", "thumbnail")


class LatestJobSerializer(serializers.Serializer):
    # Serializer puro para não importar a app processing.
    id = serializers.IntegerField()
    status = serializers.CharField()
    progress = serializers.IntegerField()
    attempts = serializers.IntegerField()
    error_message = serializers.CharField()
    started_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField()


# --------------------------------------------------------------------------- saída


class VideoListSerializer(serializers.ModelSerializer):
    # Depende do select_related("owner") no queryset (senão, N+1).
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    tags = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    thumbnail = serializers.ImageField(source="metadata.thumbnail", read_only=True)

    class Meta:
        model = Video
        fields = (
            "id",
            "title",
            "status",
            "visibility",
            "owner_username",
            "tags",
            "thumbnail",
            "is_processing",
            "created_at",
        )
        read_only_fields = fields


class VideoDetailSerializer(VideoListSerializer):
    metadata = VideoMetadataSerializer(read_only=True)
    latest_job = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    can_reprocess = serializers.SerializerMethodField()

    class Meta(VideoListSerializer.Meta):
        fields = (
            *VideoListSerializer.Meta.fields,
            "description",
            "metadata",
            "latest_job",
            "is_owner",
            "can_reprocess",
            "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(LatestJobSerializer(allow_null=True))
    def get_latest_job(self, obj):
        # jobs.all() usa o prefetch do selector; .order_by()/.latest() fariam 1 query por vídeo.
        jobs = list(obj.jobs.all())
        return LatestJobSerializer(jobs[0]).data if jobs else None

    def get_is_owner(self, obj) -> bool:
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.owner_id == request.user.id)

    def get_can_reprocess(self, obj) -> bool:
        # Só para a interface; o service revalida com lock.
        return self.get_is_owner(obj) and obj.can_be_reprocessed()


class DashboardStatsSerializer(serializers.Serializer):
    class TopCommentedSerializer(serializers.Serializer):
        id = serializers.IntegerField()
        title = serializers.CharField()
        comments_count = serializers.IntegerField()

    total_videos = serializers.IntegerField()
    by_status = serializers.DictField(child=serializers.IntegerField())
    total_duration_seconds = serializers.IntegerField()
    top_commented = TopCommentedSerializer(many=True)


# --------------------------------------------------------------------------- entrada


class VideoUploadSerializer(serializers.ModelSerializer):
    # Só entrada: quem cria é o services.create_video() (também cria o job e enfileira).
    tags = serializers.SlugRelatedField(
        many=True, slug_field="name", queryset=Tag.objects.all(), required=False
    )

    class Meta:
        model = Video
        fields = ("title", "description", "file", "visibility", "tags")

    def validate_file(self, value):
        extension = Path(value.name).suffix.lower()
        allowed = settings.VIDEO_ALLOWED_EXTENSIONS
        if extension not in allowed:
            raise serializers.ValidationError(
                f"Extensão {extension or '(nenhuma)'} não permitida. Use: {', '.join(allowed)}."
            )
        max_mb = settings.VIDEO_MAX_UPLOAD_SIZE_MB
        if value.size > max_mb * 1024 * 1024:
            raise serializers.ValidationError(f"O arquivo passa do limite de {max_mb} MB.")
        return value


class VideoUpdateSerializer(serializers.ModelSerializer):
    # Sem o arquivo: trocá-lo exigiria reprocessar.
    tags = serializers.SlugRelatedField(
        many=True, slug_field="name", queryset=Tag.objects.all(), required=False
    )

    class Meta:
        model = Video
        fields = ("title", "description", "visibility", "tags")


# --------------------------------------------------------------------------- comentários


class CommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Comment
        fields = ("id", "text", "author", "author_username", "created_at")
        # author vem do request.user, nunca do corpo.
        read_only_fields = ("id", "author", "created_at")
