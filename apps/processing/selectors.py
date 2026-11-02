from apps.processing.models import ProcessingJob


def job_queryset(*, user):
    qs = ProcessingJob.objects.select_related("video")
    if getattr(user, "is_admin", False):
        return qs
    return qs.filter(video__owner=user, video__is_deleted=False)
