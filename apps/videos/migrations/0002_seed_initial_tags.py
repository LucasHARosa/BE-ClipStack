# Data migration: altera DADOS (não o schema). Roda uma vez, em todo ambiente, na ordem certa.

from django.db import migrations

INITIAL_TAGS = ["educação", "gameplay", "música", "tecnologia", "tutorial", "vlog"]


def create_tags(apps, schema_editor):
    # apps.get_model(): usa o model "histórico", do jeito que ele estava NESTA migration.
    # Importar apps.videos.models.Tag aqui quebraria no futuro, quando o model mudar.
    Tag = apps.get_model("videos", "Tag")
    for name in INITIAL_TAGS:
        Tag.objects.get_or_create(name=name)


def delete_tags(apps, schema_editor):
    # Função reversa: permite `migrate videos 0001` (rollback) sem erro.
    Tag = apps.get_model("videos", "Tag")
    Tag.objects.filter(name__in=INITIAL_TAGS, videos__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("videos", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_tags, delete_tags),
    ]
