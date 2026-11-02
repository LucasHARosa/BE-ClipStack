import factory

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    message = factory.Sequence(lambda n: f"Notificação {n}")
