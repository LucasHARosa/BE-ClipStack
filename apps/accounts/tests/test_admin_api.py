import pytest
from django.urls import reverse

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_regular_user_cannot_list_users(auth_client):
    assert auth_client.get(reverse("admin-user-list")).status_code == 403


def test_admin_lists_users_with_video_count(admin_client, user):
    response = admin_client.get(reverse("admin-user-list"))
    assert response.status_code == 200
    row = next(u for u in response.data["results"] if u["email"] == user.email)
    assert row["videos_count"] == 0


def test_admin_promotes_user_and_is_staff_follows(admin_client, user):
    url = reverse("admin-user-set-role", args=[user.pk])
    response = admin_client.post(url, {"role": "ADMIN"}, format="json")

    user.refresh_from_db()
    assert response.status_code == 200
    assert (user.role, user.is_staff) == (User.Role.ADMIN, True)


def test_admin_cannot_change_own_role(admin_client, admin_user):
    url = reverse("admin-user-set-role", args=[admin_user.pk])
    response = admin_client.post(url, {"role": "USER"}, format="json")

    assert response.status_code == 409
    assert response.data["error"]["code"] == "cannot_change_own_role"


def test_invalid_role_is_400(admin_client, user):
    url = reverse("admin-user-set-role", args=[user.pk])
    assert admin_client.post(url, {"role": "ROOT"}, format="json").status_code == 400
