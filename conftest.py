"""Fixtures globais dos testes (o pytest carrega este arquivo sozinho, sem import).

Fixture = função que prepara algo para o teste; o pytest a injeta pelo NOME do parâmetro:
def test_x(auth_client, user): ...
"""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import AdminFactory, UserFactory


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    # autouse: vale para TODOS os testes. Uploads e thumbnails vão para uma pasta temporária
    # (tmp_path é uma fixture nativa do pytest, apagada depois).
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(autouse=True)
def _clear_cache():
    # O cache (LocMem nos testes) guarda contadores de throttling e estatísticas; limpar antes
    # de cada teste evita que um teste herde 429 ou cache de outro.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory(username="alice", email="alice@example.com")


@pytest.fixture
def other_user(db):
    return UserFactory(username="bob", email="bob@example.com")


# Os nomes admin_user e admin_client existem no pytest-django (superuser + Client do Django).
# Aqui eles são SOBRESCRITOS: um usuário com role ADMIN (não superuser) e um APIClient com JWT,
# que é o que a API usa.
@pytest.fixture
def admin_user(db):
    return AdminFactory(username="moderador", email="mod@example.com")


def _jwt_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def auth_client(user):
    # JWT de verdade (passa pela JWTAuthentication), não force_authenticate.
    return _jwt_client(user)


@pytest.fixture
def other_client(other_user):
    return _jwt_client(other_user)


@pytest.fixture
def admin_client(admin_user):
    return _jwt_client(admin_user)


@pytest.fixture
def client_for():
    # Fixture "fábrica": devolve uma função. Útil quando o teste precisa de vários clientes.
    return _jwt_client
