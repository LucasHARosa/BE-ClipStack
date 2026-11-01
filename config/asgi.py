"""Ponto de entrada ASGI (assíncrono), usado por servidores como Uvicorn/Daphne.

Só sob ASGI as views async ganham concorrência real; sob WSGI o Django as roda numa
thread com event loop próprio (detalhes na etapa 9, health check).
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()
