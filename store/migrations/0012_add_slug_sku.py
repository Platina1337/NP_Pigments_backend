from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    Perfume = apps.get_model("store", "Perfume")
    Pigment = apps.get_model("store", "Pigment")
    for model in (Perfume, Pigment):
        for obj in model.objects.filter(slug__isnull=True) | model.objects.filter(slug=""):
            base = slugify(obj.name) or f"{obj._meta.model_name}-{obj.pk}"
            slug = base
            counter = 1
            while model.objects.filter(slug=slug).exclude(pk=obj.pk).exists():
                counter += 1
                slug = f"{base}-{counter}"
            obj.slug = slug
            obj.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0011_perfume_discount_end_date_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="perfume",
            name="slug",
            field=models.SlugField(blank=True, null=True, unique=True, verbose_name="Slug"),
        ),
        migrations.AddField(
            model_name="perfume",
            name="sku",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True, verbose_name="Артикул"),
        ),
        migrations.AddField(
            model_name="pigment",
            name="slug",
            field=models.SlugField(blank=True, null=True, unique=True, verbose_name="Slug"),
        ),
        migrations.AddField(
            model_name="pigment",
            name="sku",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True, verbose_name="Артикул"),
        ),
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
    ]

