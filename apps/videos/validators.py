from pathlib import Path

from django.conf import settings
from rest_framework import serializers


def validate_video_extension(file):
    extension = Path(file.name).suffix.lower()
    allowed = settings.VIDEO_ALLOWED_EXTENSIONS
    if extension not in allowed:
        raise serializers.ValidationError(
            f"Extensão {extension or '(nenhuma)'} não permitida. Use: {', '.join(allowed)}."
        )


def validate_video_size(file):
    max_mb = settings.VIDEO_MAX_UPLOAD_SIZE_MB
    if file.size > max_mb * 1024 * 1024:
        raise serializers.ValidationError(f"O arquivo passa do limite de {max_mb} MB.")
