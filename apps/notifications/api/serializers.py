from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    # Somente leitura: marcar como lida é uma ação (POST mark-all-read), não um PATCH livre.
    class Meta:
        model = Notification
        fields = ("id", "message", "video", "is_read", "created_at")
        read_only_fields = fields
