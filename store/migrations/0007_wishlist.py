from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('store', '0006_productimage'),
    ]

    operations = [
        migrations.CreateModel(
            name='Wishlist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='wishlist', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Избранное',
                'verbose_name_plural': 'Избранное',
            },
        ),
        migrations.CreateModel(
            name='WishlistItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('perfume', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='store.perfume')),
                ('pigment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='store.pigment')),
                ('wishlist', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='store.wishlist')),
            ],
            options={
                'verbose_name': 'Элемент избранного',
                'verbose_name_plural': 'Элементы избранного',
            },
        ),
        migrations.AlterUniqueTogether(
            name='wishlistitem',
            unique_together={('wishlist', 'perfume', 'pigment')},
        ),
    ]

