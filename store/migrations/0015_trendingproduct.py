from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0014_promotion'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrendingProduct',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_type', models.CharField(choices=[('perfume', 'Парфюм'), ('pigment', 'Пигмент')], max_length=10, verbose_name='Тип товара')),
                ('position', models.PositiveIntegerField(default=0, verbose_name='Позиция')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('perfume', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='store.perfume', verbose_name='Парфюм')),
                ('pigment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='store.pigment', verbose_name='Пигмент')),
            ],
            options={
                'verbose_name': 'Трендовый товар',
                'verbose_name_plural': 'Трендовые товары',
                'ordering': ['position', '-created_at'],
            },
        ),
    ]









