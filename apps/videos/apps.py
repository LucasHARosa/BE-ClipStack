from django.apps import AppConfig


class VideosConfig(AppConfig):
    name = "apps.videos"
    verbose_name = "Vídeos"

    def ready(self):
        from apps.videos import signals  # noqa: F401
