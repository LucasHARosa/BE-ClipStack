import factory

from apps.accounts.tests.factories import UserFactory
from apps.videos.models import Comment, Tag, Video, VideoMetadata


class TagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tag
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"tag-{n}")


class VideoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Video

    # SubFactory: cria o dono junto (ou use VideoFactory(owner=alguem)).
    owner = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Vídeo {n}")
    description = ""
    # Arquivo de verdade no storage (MEDIA_ROOT temporário dos testes).
    file = factory.django.FileField(filename="clip.mp4", data=b"0" * 2048)
    status = Video.Status.COMPLETED
    visibility = Video.Visibility.PUBLIC

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        # VideoFactory(tags=[tag1, tag2]) → define o ManyToMany depois de salvar.
        if create and extracted:
            self.tags.set(extracted)


class VideoMetadataFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VideoMetadata

    video = factory.SubFactory(VideoFactory)
    duration_seconds = 60
    resolution = "1280x720"


class CommentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Comment

    video = factory.SubFactory(VideoFactory)
    author = factory.SubFactory(UserFactory)
    text = factory.Faker("sentence", locale="pt_BR")
