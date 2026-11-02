from unittest import mock

import pytest
from django.urls import reverse

from apps.notifications import services, tasks
from apps.notifications.models import Notification
from apps.notifications.tests.factories import NotificationFactory
from apps.videos.tests.factories import VideoFactory

pytestmark = pytest.mark.django_db

LIST = reverse("notification-list")


class TestNotifyVideoProcessed:
    def test_creates_notification_and_schedules_email_after_commit(
        self, user, django_capture_on_commit_callbacks
    ):
        video = VideoFactory(owner=user, title="Clipe")
        with (
            mock.patch.object(tasks.send_notification_email, "delay") as send,
            django_capture_on_commit_callbacks(execute=True),
        ):
            notification = services.notify_video_processed(
                video_id=video.pk, succeeded=True, event_key="job:1:finished"
            )
        assert notification.user == user
        assert notification.message == 'Seu vídeo "Clipe" está pronto.'
        send.assert_called_once_with(notification.pk)

    def test_is_idempotent_by_event_key(self, user):
        video = VideoFactory(owner=user)
        with mock.patch.object(tasks.send_notification_email, "delay"):
            first = services.notify_video_processed(
                video_id=video.pk, succeeded=False, event_key="job:7:finished"
            )
            second = services.notify_video_processed(
                video_id=video.pk, succeeded=False, event_key="job:7:finished"
            )
        assert first.pk == second.pk
        assert Notification.objects.filter(user=user).count() == 1


class TestEmail:
    def test_sends_once_using_mailoutbox(self, user, mailoutbox):
        notification = NotificationFactory(user=user, message="Seu vídeo está pronto.")

        tasks.send_notification_email(notification.pk)
        tasks.send_notification_email(notification.pk)  # retry/entrega duplicada

        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [user.email]
        assert mailoutbox[0].body == "Seu vídeo está pronto."
        notification.refresh_from_db()
        assert notification.emailed_at is not None


class TestApi:
    def test_lists_only_own_notifications_even_for_admin(self, admin_client, admin_user, user):
        NotificationFactory(user=user)
        mine = NotificationFactory(user=admin_user)
        results = admin_client.get(LIST).data["results"]
        assert [n["id"] for n in results] == [mine.pk]

    def test_cursor_pagination_is_stable_with_new_items(self, auth_client, user):
        NotificationFactory.create_batch(25, user=user)
        first_page = auth_client.get(LIST).data
        NotificationFactory(user=user, message="nova")  # chega entre as páginas

        second_page = auth_client.get(first_page["next"]).data

        assert "count" not in first_page  # cursor não tem total
        first_ids = {n["id"] for n in first_page["results"]}
        second_ids = {n["id"] for n in second_page["results"]}
        assert len(first_page["results"]) == 20
        assert first_ids.isdisjoint(second_ids)  # nada repetido
        assert len(second_page["results"]) == 5

    def test_mark_all_read(self, auth_client, user):
        NotificationFactory.create_batch(3, user=user)
        response = auth_client.post(reverse("notification-mark-all-read"))
        assert response.data == {"updated": 3}
        assert not Notification.objects.filter(user=user, is_read=False).exists()
