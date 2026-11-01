"""Settings de produção. Tudo sensível vem de variáveis de ambiente."""

from .base import *  # noqa: F403
from .base import env

DEBUG = False
# Sem default: em produção, esquecer ALLOWED_HOSTS deve quebrar o boot, não liberar tudo.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# A app roda atrás de um proxy (Nginx/load balancer) que termina o HTTPS e avisa por header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# HSTS (HTTP Strict Transport Security): o navegador passa a só usar HTTPS neste domínio.
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# HSTS preload fica desligado de propósito (o check --deploy avisa, W021): entrar na lista de
# preload dos navegadores é difícil de desfazer, então é uma decisão para o domínio final.
SECURE_CONTENT_TYPE_NOSNIFF = True

EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
