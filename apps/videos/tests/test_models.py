import pytest
from django.contrib.auth.models import AnonymousUser

from apps.accounts.tests.factories import AdminFactory, UserFactory
from apps.videos.models import Video
from apps.videos.tests.factories import VideoFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog(user, other_user):
    # Um cenário pequeno, nomeado, reutilizado pelos testes do QuerySet.
    return {
        "alice_public": VideoFactory(owner=user, title="alice público"),
        "alice_private": VideoFactory(owner=user, title="alice privado", visibility="private"),
        "alice_processing": VideoFactory(
            owner=user, title="alice processando", status="processing"
        ),
        "bob_public": VideoFactory(owner=other_user, title="bob público"),
        "bob_private": VideoFactory(owner=other_user, title="bob privado", visibility="private"),
        "bob_deleted": VideoFactory(owner=other_user, title="bob apagado", is_deleted=True),
    }


def titles(qs):
    return sorted(v.title for v in qs)


class TestVisibleTo:
    def test_owner_sees_all_own_plus_public_completed_of_others(self, catalog, user):
        assert titles(Video.objects.visible_to(user)) == sorted(
            ["alice público", "alice privado", "alice processando", "bob público"]
        )

    def test_admin_sees_everything_not_deleted(self, catalog):
        assert "bob privado" in titles(Video.objects.visible_to(AdminFactory()))
        assert "bob apagado" not in titles(Video.objects.visible_to(AdminFactory()))

    def test_anonymous_sees_only_public_completed(self, catalog):
        assert titles(Video.objects.visible_to(AnonymousUser())) == ["alice público", "bob público"]

    def test_querysets_are_chainable(self, catalog, user):
        assert titles(Video.objects.visible_to(user).completed().owned_by(user)) == [
            "alice privado",
            "alice público",
        ]


class TestVideoMethods:
    @pytest.mark.parametrize(
        ("status", "is_deleted", "expected"),
        [
            ("failed", False, True),
            ("failed", True, False),
            ("completed", False, False),
            ("processing", False, False),
        ],
    )
    def test_can_be_reprocessed(self, status, is_deleted, expected):
        # parametrize: o mesmo teste roda uma vez para cada linha da tabela.
        video = VideoFactory.build(status=status, is_deleted=is_deleted)
        assert video.can_be_reprocessed() is expected

    @pytest.mark.parametrize(
        ("status", "expected"), [("queued", True), ("processing", True), ("completed", False)]
    )
    def test_is_processing_property(self, status, expected):
        assert VideoFactory.build(status=status).is_processing is expected


def test_owner_with_videos_cannot_be_deleted():
    from django.db.models import ProtectedError

    owner = UserFactory()
    VideoFactory(owner=owner)
    with pytest.raises(ProtectedError):
        owner.delete()
