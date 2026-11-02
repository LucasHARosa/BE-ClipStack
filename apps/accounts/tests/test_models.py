import pytest

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db  # todos os testes deste módulo usam o banco


def test_admin_role_sets_is_staff():
    user = UserFactory()
    assert user.is_staff is False

    user.role = User.Role.ADMIN
    user.save()

    assert user.is_staff is True
    assert user.is_admin is True


def test_demoting_admin_removes_is_staff():
    user = UserFactory(role=User.Role.ADMIN)
    user.role = User.Role.USER
    user.save()
    assert user.is_staff is False


def test_create_superuser_is_always_admin():
    su = User.objects.create_superuser(username="root", email="root@x.com", password="x")
    assert su.role == User.Role.ADMIN
    assert su.is_staff is True


def test_email_is_the_login_field():
    assert User.USERNAME_FIELD == "email"
    assert str(UserFactory(email="a@x.com")) == "a@x.com"
