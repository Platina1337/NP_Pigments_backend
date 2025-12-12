from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0013_alter_perfume_slug_alter_pigment_slug'),
    ]

    operations = [
        migrations.CreateModel(
            name='Promotion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=255, verbose_name='Название акции')),
                ('promo_type', models.CharField(choices=[('brand', 'Бренд'), ('category', 'Категория'), ('manual', 'Ручной выбор'), ('all', 'Все товары')], default='manual', max_length=20, verbose_name='Тип акции')),
                ('slot', models.CharField(choices=[('homepage_deals_1', 'Главная — блок акций 1'), ('homepage_deals_2', 'Главная — блок акций 2'), ('homepage_deals_3', 'Главная — блок акций 3')], default='homepage_deals_1', max_length=50, verbose_name='Слот показа')),
                ('priority', models.IntegerField(default=0, verbose_name='Приоритет (меньше — выше)')),
                ('active', models.BooleanField(default=False, verbose_name='Активна')),
                ('start_at', models.DateTimeField(blank=True, null=True, verbose_name='Начало акции')),
                ('end_at', models.DateTimeField(blank=True, null=True, verbose_name='Конец акции')),
                ('discount_percentage', models.PositiveIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Скидка, %')),
                ('discount_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Фиксированная цена со скидкой')),
                ('apply_prices', models.BooleanField(default=True, verbose_name='Применять скидку к товарам')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('brand', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='store.brand', verbose_name='Бренд')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='store.category', verbose_name='Категория')),
            ],
            options={
                'verbose_name': 'Акция',
                'verbose_name_plural': 'Акции',
                'ordering': ['priority', '-created_at'],
            },
        ),
        migrations.AddField(
            model_name='perfume',
            name='discount_source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='discounted_perfumes', to='store.promotion', verbose_name='Источник акции'),
        ),
        migrations.AddField(
            model_name='pigment',
            name='discount_source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='discounted_pigments', to='store.promotion', verbose_name='Источник акции'),
        ),
        migrations.AddField(
            model_name='promotion',
            name='perfumes',
            field=models.ManyToManyField(blank=True, related_name='promotions', to='store.perfume', verbose_name='Парфюмы'),
        ),
        migrations.AddField(
            model_name='promotion',
            name='pigments',
            field=models.ManyToManyField(blank=True, related_name='promotions', to='store.pigment', verbose_name='Пигменты'),
        ),
    ]

