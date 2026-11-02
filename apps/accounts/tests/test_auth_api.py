import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.accounts.tests.factories import TEST_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

REGISTER = reverse("auth-register")
LOGIN = reverse("auth-login")
REFRESH = reverse("auth-refresh")
LOGOUT = reverse("auth-logout")
ME = reverse("users-me")


def register_payload(**overrides):
    return {
        "email": "nova@example.com",
        "username": "nova",
        "password": TEST_PASSWORD,
        "password_confirm": TEST_PASSWORD,
        **overrides,
    }


class TestRegister:
    def test_creates_user_with_hashed_password_and_ignores_role(self, api_client):
        response = api_client.post(REGISTER, register_payload(role="ADMIN"), format="json")

        assert response.status_code == 201
        assert "password" not in response.data
        user = User.objects.get(email="nova@example.com")
        assert user.role == User.Role.USER  # role é read_only: mass assignment ignorado
        assert user.check_password(TEST_PASSWORD)

    def test_password_confirmation_mismatch(self, api_client):
        response = api_client.post(
            REGISTER, register_payload(password_confirm="outra"), format="json"
        )
        assert response.status_code == 400
        # formato padronizado de erro: {"error": {"code", "message", "details"}}
        assert response.data["error"]["code"] == "validation_error"
        assert "password_confirm" in response.data["error"]["details"]

    def test_duplicate_email_uses_model_unique_validator(self, api_client, user):
        response = api_client.post(REGISTER, register_payload(email=user.email), format="json")
        assert response.status_code == 400
        assert "email" in response.data["error"]["details"]

    def test_weak_password(self, api_client):
        response = api_client.post(
            REGISTER, register_payload(password="123", password_confirm="123"), format="json"
        )
        assert response.status_code == 400
        assert "password" in response.data["error"]["details"]


class TestLoginRefreshLogout:
    def test_login_returns_tokens_with_ui_claims(self, api_client, user):
        response = api_client.post(
            LOGIN, {"email": user.email, "password": TEST_PASSWORD}, format="json"
        )
        assert response.status_code == 200
        claims = AccessToken(response.data["access"])
        assert claims["role"] == "USER"
        assert claims["username"] == user.username

    def test_wrong_password_is_401(self, api_client, user):
        response = api_client.post(LOGIN, {"email": user.email, "password": "x"}, format="json")
        assert response.status_code == 401

    def test_inactive_user_cannot_login(self, api_client):
        inactive = UserFactory(is_active=False)
        response = api_client.post(
            LOGIN, {"email": inactive.email, "password": TEST_PASSWORD}, format="json"
        )
        assert response.status_code == 401

    def test_refresh_rotates_and_blacklists_the_old_token(self, api_client, user):
        tokens = api_client.post(
            LOGIN, {"email": user.email, "password": TEST_PASSWORD}, format="json"
        ).data

        rotated = api_client.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")
        reused = api_client.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")

        assert rotated.status_code == 200
        assert rotated.data["refresh"] != tokens["refresh"]
        assert reused.status_code == 401

    def test_logout_blacklists_refresh(self, api_client, user):
        tokens = api_client.post(
            LOGIN, {"email": user.email, "password": TEST_PASSWORD}, format="json"
        ).data

        assert (
            api_client.post(LOGOUT, {"refresh": tokens["refresh"]}, format="json").status_code
            == 200
        )
        assert (
            api_client.post(REFRESH, {"refresh": tokens["refresh"]}, format="json").status_code
            == 401
        )


class TestAuthenticationOnRequests:
    def test_missing_token_is_401_with_bearer_challenge(self, api_client):
        response = api_client.get(ME)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"].startswith("Bearer")
        assert response.data["error"]["code"] == "not_authenticated"

    def test_permissions_read_role_from_database_not_from_token(self, client_for, admin_user):
        client = client_for(admin_user)  # token emitido com claim role=ADMIN
        User.objects.filter(pk=admin_user.pk).update(role="USER", is_staff=False)

        response = client.get(reverse("admin-user-list"))

        assert response.status_code == 403

    def test_deactivated_user_with_valid_token_is_401(self, auth_client, user):
        User.objects.filter(pk=user.pk).update(is_active=False)
        assert auth_client.get(ME).status_code == 401


class TestMe:
    def test_patch_changes_only_username(self, auth_client, user):
        response = auth_client.patch(
            ME, {"username": "alice2", "role": "ADMIN", "email": "x@x.com"}, format="json"
        )
        user.refresh_from_db()
        assert response.status_code == 200
        assert (user.username, user.role, user.email) == ("alice2", "USER", "alice@example.com")

    def test_put_is_not_allowed(self, auth_client):
        assert auth_client.put(ME, {}, format="json").status_code == 405
