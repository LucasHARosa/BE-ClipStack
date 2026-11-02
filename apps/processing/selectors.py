from apps.processing.models import ProcessingJob


def visible_jobs(*, user):
    jobs = ProcessingJob.objects.select_related("video")
    if getattr(user, "is_admin", False):
        return jobs
    return jobs.filter(video__owner=user, video__is_deleted=False)
