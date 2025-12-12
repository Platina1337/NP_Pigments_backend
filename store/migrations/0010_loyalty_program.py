from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('store', '0009_emailotp_register_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoyaltyAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance', models.PositiveIntegerField(default=0, verbose_name='Баллы на счете')),
                ('lifetime_earned', models.PositiveIntegerField(default=0, verbose_name='Всего начислено')),
                ('lifetime_redeemed', models.PositiveIntegerField(default=0, verbose_name='Всего потрачено')),
                ('tier', models.CharField(choices=[('bronze', 'Бронза'), ('silver', 'Серебро'), ('gold', 'Золото')], default='bronze', max_length=20, verbose_name='Уровень')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='loyalty_account', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Счет лояльности',
                'verbose_name_plural': 'Счета лояльности',
            },
        ),
        migrations.CreateModel(
            name='LoyaltyTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(choices=[('earn', 'Начисление'), ('redeem', 'Списание'), ('refund', 'Возврат списания'), ('adjust', 'Корректировка')], max_length=20)),
                ('points', models.IntegerField(verbose_name='Изменение баллов (может быть отрицательным)')),
                ('description', models.TextField(blank=True, verbose_name='Комментарий')),
                ('balance_after', models.IntegerField(default=0, verbose_name='Баланс после операции')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='loyalty_transactions', to='store.order')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='loyalty_transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Транзакция лояльности',
                'verbose_name_plural': 'Транзакции лояльности',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='order',
            name='loyalty_awarded',
            field=models.BooleanField(default=False, verbose_name='Баллы начислены'),
        ),
        migrations.AddField(
            model_name='order',
            name='loyalty_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Скидка баллами'),
        ),
        migrations.AddField(
            model_name='order',
            name='loyalty_points_earned',
            field=models.PositiveIntegerField(default=0, verbose_name='Начисленные баллы'),
        ),
        migrations.AddField(
            model_name='order',
            name='loyalty_points_used',
            field=models.PositiveIntegerField(default=0, verbose_name='Потраченные баллы'),
        ),
        migrations.AddField(
            model_name='order',
            name='loyalty_refunded',
            field=models.BooleanField(default=False, verbose_name='Баллы возвращены'),
        ),
    ]

