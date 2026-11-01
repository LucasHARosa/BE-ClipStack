from django.contrib import admin
from django.db.models import Count

from apps.core.admin import ModerationAdminMixin

from . import services
from .models import Comment, Tag, Video, VideoMetadata


class VideoMetadataInline(ModerationAdminMixin, admin.StackedInline):
    # Inline: edita/mostra o model relacionado dentro da página do vídeo.
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
    # list_select_related: JOIN com o owner na listagem (evita 1 query por linha para o email).
    list_select_related = ("owner",)
    autocomplete_fields = ("owner",)
    filter_horizontal = ("tags",)
    date_hierarchy = "created_at"
    # O inline de jobs é adicionado pela app processing (apps/processing/admin.py).
    inlines = [VideoMetadataInline]
    actions = ["hide_videos"]

    # Admin action: moderação em lote. Passa pelo MESMO service da API (soft delete), em vez
    # do "delete_selected" padrão, que apagaria a linha do banco.
    @admin.action(description="Ocultar vídeos selecionados (moderação)", permissions=["moderate"])
    def hide_videos(self, request, queryset):
        for video in queryset.filter(is_deleted=False):
            services.delete_video(video=video, actor=request.user)
        self.message_user(request, "Vídeos ocultados.")

    def get_queryset(self, request):
        # annotate: COUNT dos comentários no mesmo SELECT (reverso "comments" do Comment).
        return super().get_queryset(request).annotate(comments_total=Count("comments"))

    @admin.display(description="comentários", ordering="comments_total")
    def comments_count(self, obj):
        return obj.comments_total


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    # Sem o mixin: tag é configuração do sistema, gerida pelo superuser.
    list_display = ("name", "videos_count")
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(videos_total=Count("videos"))

    @admin.display(description="vídeos", ordering="videos_total")
    def videos_count(self, obj):
        return obj.videos_total


@admin.register(Comment)
class CommentAdmin(ModerationAdminMixin, admin.ModelAdmin):
    # Moderação: o ADMIN apaga comentários de qualquer um, mas não os edita.
    moderator_can_delete = True
    list_display = ("short_text", "video", "author", "created_at")
    search_fields = ("text", "author__email", "video__title")
    list_select_related = ("video", "author")
    autocomplete_fields = ("video", "author")

    @admin.display(description="texto")
    def short_text(self, obj):
        return obj.text[:60]
