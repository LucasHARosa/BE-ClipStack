"""Serializers de vídeos, tags e comentários.

Serializer valida FORMATO (tipo, tamanho, campos obrigatórios, choices) e formata a SAÍDA.
Regra de NEGÓCIO ("só reprocessa se falhou", "um job ativo por vídeo", "quem pode apagar")
fica no service, porque:
- o service também é chamado por tasks, Admin e shell, que não passam pelo serializer;
- a regra precisa de transação e lock (select_for_update), que não cabem no is_valid();
- o mesmo vídeo pode ser validado de formas diferentes (upload x update), mas a regra é uma só.
"""

from pathlib import Path

from django.conf import settings
from rest_framework import serializers

from apps.videos.models import Comment, Tag, Video, VideoMetadata


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name")


class VideoMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoMetadata
        # thumbnail: com o request no context, o DRF devolve a URL absoluta.
        fields = ("duration_seconds", "resolution", "thumbnail")


class LatestJobSerializer(serializers.Serializer):
    # Serializer puro, de SAÍDA: descreve o último ProcessingJob sem importar a app processing
    # (fronteira entre apps). Lê os atributos do objeto que receber.
    id = serializers.IntegerField()
    status = serializers.CharField()
    progress = serializers.IntegerField()
    attempts = serializers.IntegerField()
    error_message = serializers.CharField()
    started_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField()


# --------------------------------------------------------------------------- saída


class VideoListSerializer(serializers.ModelSerializer):
    # source="owner.username": lê um atributo de um objeto relacionado (atravessa a FK).
    # Sem select_related("owner") no queryset, isso gera 1 query por vídeo (N+1).
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    # SlugRelatedField: representa a relação por um campo legível (o nome) em vez do id.
    tags = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    # Atravessa o OneToOne; se o vídeo ainda não tem metadata, o DRF devolve null.
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
        # is_processing é uma @property do model; o ModelSerializer a aceita como campo
        # somente leitura.
        read_only_fields = fields


class VideoDetailSerializer(VideoListSerializer):
    # Serializers aninhados read-only: o vídeo com metadata, tags e último job numa resposta só.
    metadata = VideoMetadataSerializer(read_only=True)
    # SerializerMethodField: campo calculado por um método get_<campo>(self, obj).
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

    def get_latest_job(self, obj):
        # jobs.all() usa o cache do prefetch_related("jobs") feito no selector. Um
        # .order_by()/.latest() aqui ignoraria o cache e faria 1 query por vídeo.
        # A ordenação "-created_at" vem do Meta.ordering do ProcessingJob.
        jobs = list(obj.jobs.all())
        return LatestJobSerializer(jobs[0]).data if jobs else None

    def get_is_owner(self, obj):
        # self.context["request"]: o view do DRF injeta o request no context do serializer.
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.owner_id == request.user.id)

    def get_can_reprocess(self, obj):
        # Só para a INTERFACE decidir se mostra o botão. O service revalida tudo (com lock)
        # quando o POST /reprocess/ chegar. O admin não reprocessa vídeo dos outros (403).
        return self.get_is_owner(obj) and obj.can_be_reprocessed()


# --------------------------------------------------------------------------- entrada


class VideoUploadSerializer(serializers.ModelSerializer):
    # Serializer só de ENTRADA (multipart/form-data). A view chama is_valid() e passa o
    # validated_data para services.create_video(); NUNCA chama serializer.save(), porque
    # criar o vídeo também cria o job e enfileira o processamento. A resposta usa o
    # VideoDetailSerializer: entrada e saída têm formatos diferentes.
    tags = serializers.SlugRelatedField(
        many=True, slug_field="name", queryset=Tag.objects.all(), required=False
    )

    class Meta:
        model = Video
        fields = ("title", "description", "file", "visibility", "tags")

    # validate_<campo>(): validação de UM campo isolado. Roda antes do validate().
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
    # PATCH: o arquivo não pode ser trocado (exigiria reprocessar); só os dados descritivos.
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
        # author e video vêm do contexto da requisição (request.user e a URL aninhada),
        # nunca do corpo: senão daria para comentar em nome de outra pessoa.
        read_only_fields = ("id", "author", "created_at")
