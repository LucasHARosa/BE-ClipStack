from django.apps import AppConfig


class VideosConfig(AppConfig):
    # name: caminho de import da app (as apps ficam dentro do pacote "apps").
    name = "apps.videos"
    verbose_name = "Vídeos"

    def ready(self):
        # ready(): roda uma vez, quando o registro de apps termina de carregar. É o lugar de
        # conectar os signals (o import registra os @receiver).
        from apps.videos import signals  # noqa: F401
