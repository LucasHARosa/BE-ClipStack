import factory

from apps.accounts.models import User

TEST_PASSWORD = "S3nh@-forte-123"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    role = User.Role.USER
    password = factory.PostGenerationMethodCall("set_password", TEST_PASSWORD)

    @classmethod
    def _after_postgeneration(cls, instance, create, results=None):
        # set_password não salva sozinho; sem isso o hash ficaria só em memória.
        if create and results:
            instance.save()


class AdminFactory(UserFactory):
    role = User.Role.ADMIN
