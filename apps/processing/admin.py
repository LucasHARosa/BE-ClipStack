from django.contrib import admin

from apps.core.admin import ModerationAdminMixin
from apps.videos.admin import VideoAdmin
from apps.videos.models import Video

from .models import ProcessingJob


class ProcessingJobInline(ModerationAdminMixin, admin.TabularInline):
    model = ProcessingJob
    extra = 0
    can_delete = False
    fields = ("status", "progress", "attempts", "error_message", "started_at", "finished_at")
    readonly_fields = fields
    show_change_link = True


# videos não pode importar processing, então é processing que estende o admin do vídeo.
# Depende de videos vir antes no INSTALLED_APPS.
admin.site.unregister(Video)


@admin.register(Video)
class VideoWithJobsAdmin(VideoAdmin):
    inlines = [*VideoAdmin.inlines, ProcessingJobInline]


@admin.register(ProcessingJob)
class ProcessingJobAdmin(ModerationAdminMixin, admin.ModelAdmin):
    list_display = ("id", "video", "status", "progress", "attempts", "started_at", "finished_at")
    list_filter = ("status",)
    search_fields = ("video__title",)
    list_select_related = ("video",)
    readonly_fields = ("created_at",)
