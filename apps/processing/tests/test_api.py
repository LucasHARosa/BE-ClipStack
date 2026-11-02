import pytest
from django.urls import reverse

from apps.processing.tests.factories import ProcessingJobFactory
from apps.videos.tests.factories import VideoFactory

pytestmark = pytest.mark.django_db

LIST = reverse("job-list")


def ids(response):
    return sorted(j["id"] for j in response.data["results"])


def test_jobs_visibility(auth_client, other_client, admin_client, user, other_user):
    mine = ProcessingJobFactory(video=VideoFactory(owner=user))
    theirs = ProcessingJobFactory(video=VideoFactory(owner=other_user))
    ProcessingJobFactory(video=VideoFactory(owner=user, is_deleted=True))  # vídeo apagado

    assert ids(auth_client.get(LIST)) == [mine.pk]
    assert ids(other_client.get(LIST)) == [theirs.pk]
    assert len(admin_client.get(LIST).data["results"]) == 3  # admin vê todos


def test_job_of_another_user_is_404(auth_client, other_user):
    job = ProcessingJobFactory(video=VideoFactory(owner=other_user))
    assert auth_client.get(reverse("job-detail", args=[job.pk])).status_code == 404


def test_filter_by_status(auth_client, user):
    failed = ProcessingJobFactory(video=VideoFactory(owner=user), status="failed")
    ProcessingJobFactory(video=VideoFactory(owner=user), status="completed")
    assert ids(auth_client.get(LIST, {"status": "failed"})) == [failed.pk]
