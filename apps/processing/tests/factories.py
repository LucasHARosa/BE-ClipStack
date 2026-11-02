import factory

from apps.processing.models import ProcessingJob
from apps.videos.models import Video
from apps.videos.tests.factories import VideoFactory


class ProcessingJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProcessingJob

    video = factory.SubFactory(VideoFactory, status=Video.Status.QUEUED)
    status = ProcessingJob.Status.QUEUED
