"""Settings de desenvolvimento local."""

from .base import *  # noqa: F403
from .base import INSTALLED_APPS, MIDDLEWARE, REST_FRAMEWORK, env

DEBUG = True
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Em dev, o API Browsable do DRF ajuda a explorar os endpoints pelo navegador.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

# django-debug-toolbar: mostra queries SQL, tempo e cache de cada página. Só em dev.
INSTALLED_APPS += ["debug_toolbar"]
# Entra o mais cedo possível, mas depois de middlewares que codificam a resposta (ex.: GZip).
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
INTERNAL_IPS = ["127.0.0.1"]

# Emails impressos no console em vez de enviados.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
