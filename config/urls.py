"""URLs raiz. A API fica versionada pela URL: tudo de /api/v1/ está em config/api_v1.py."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("config.api_v1")),
    # OpenAPI: o schema (YAML/JSON) e o Swagger UI que o consome. Públicos.
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    # Em dev o próprio Django serve os arquivos de mídia; em produção é o storage/Nginx.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Login/logout por sessão do API navegável do DRF (só para explorar a API no navegador).
    urlpatterns += [path("api-auth/", include("rest_framework.urls"))]

    if "debug_toolbar" in settings.INSTALLED_APPS:
        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
elif settings.SERVE_MEDIA:
    # Compose local com Gunicorn (DEBUG=False): o static() acima não funciona sem DEBUG.
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
