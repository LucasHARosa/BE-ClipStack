from django.contrib import admin
from django.db.models import Count

from apps.core.admin import ModerationAdminMixin

from . import services
from .models import Comment, Tag, Video, VideoMetadata


class VideoMetadataInline(ModerationAdminMixin, admin.StackedInline):
    model = VideoMetadata
    can_delete = False


@admin.register(Video)
class VideoAdmin(ModerationAdminMixin, admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "status",
        "visibility",
        "is_deleted",
        "comments_count",
        "created_at",
    )
    list_filter = ("status", "visibility", "is_deleted", "tags")
    search_fields = ("title", "owner__email")
    list_select_related = ("owner",)
    autocomplete_fields = ("owner",)
    filter_horizontal = ("tags",)
    date_hierarchy = "created_at"
    # O inline de jobs é adicionado pela app processing (videos não a importa).
    inlines = [VideoMetadataInline]
    actions = ["hide_videos"]

    # Mesmo service da API (soft delete); o delete_selected padrão apagaria a linha.
    @admin.action(description="Ocultar vídeos selecionados (moderação)", permissions=["moderate"])
    def hide_videos(self, request, queryset):
        for video in queryset.filter(is_deleted=False):
            services.delete_video(video=video, actor=request.user)
        self.message_user(request, "Vídeos ocultados.")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(comments_total=Count("comments"))

    @admin.display(description="comentários", ordering="comments_total")
    def comments_count(self, obj):
        return obj.comments_total


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "videos_count")
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(videos_total=Count("videos"))

    @admin.display(description="vídeos", ordering="videos_total")
    def videos_count(self, obj):
        return obj.videos_total


@admin.register(Comment)
class CommentAdmin(ModerationAdminMixin, admin.ModelAdmin):
    moderator_can_delete = True
    list_display = ("short_text", "video", "author", "created_at")
    search_fields = ("text", "author__email", "video__title")
    list_select_related = ("video", "author")
    autocomplete_fields = ("video", "author")

    @admin.display(description="texto")
    def short_text(self, obj):
        return obj.text[:60]
