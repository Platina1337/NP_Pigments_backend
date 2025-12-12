from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from store.models import UserProfile, Cart, Order, Wishlist, UserSettings, CartItem, OrderItem, WishlistItem
from django.contrib.admin.models import LogEntry

# Опциональные импорты
try:
    from account.models import EmailAddress
except ImportError:
    EmailAddress = None

try:
    from socialaccount.models import SocialAccount
except ImportError:
    SocialAccount = None

try:
    from token_blacklist.models import OutstandingToken
except ImportError:
    OutstandingToken = None

User = get_user_model()

class Command(BaseCommand):
    help = 'Удаляет пользователя и все связанные данные'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email пользователя')
        parser.add_argument('--username', type=str, help='Username пользователя')

    def handle(self, *args, **options):
        email = options.get('email')
        username = options.get('username')
        
        if not email and not username:
            self.stdout.write(self.style.ERROR('Необходимо указать --email или --username'))
            return
        
        try:
            # Находим пользователя
            if email:
                user = User.objects.get(email=email)
            else:
                user = User.objects.get(username=username)
            
            user_id = user.id
            self.stdout.write(f'Найден пользователь: {user.username} ({user.email}), ID: {user_id}')
            
            # Удаляем связанные данные
            self.stdout.write('Удаление элементов корзины...')
            CartItem.objects.filter(cart__user_id=user_id).delete()
            
            self.stdout.write('Удаление корзины...')
            Cart.objects.filter(user_id=user_id).delete()
            
            self.stdout.write('Удаление элементов заказов...')
            OrderItem.objects.filter(order__user_id=user_id).delete()
            
            self.stdout.write('Удаление заказов...')
            Order.objects.filter(user_id=user_id).delete()
            
            self.stdout.write('Удаление элементов избранного...')
            WishlistItem.objects.filter(wishlist__user_id=user_id).delete()
            
            self.stdout.write('Удаление избранного...')
            Wishlist.objects.filter(user_id=user_id).delete()
            
            self.stdout.write('Удаление настроек пользователя...')
            UserSettings.objects.filter(user_id=user_id).delete()
            
            self.stdout.write('Удаление профиля...')
            UserProfile.objects.filter(user_id=user_id).delete()
            
            if EmailAddress:
                self.stdout.write('Удаление email адресов...')
                EmailAddress.objects.filter(user_id=user_id).delete()
            
            if SocialAccount:
                self.stdout.write('Удаление социальных аккаунтов...')
                SocialAccount.objects.filter(user_id=user_id).delete()
            
            if OutstandingToken:
                self.stdout.write('Удаление токенов...')
                OutstandingToken.objects.filter(user_id=user_id).delete()
            
            self.stdout.write('Удаление логов админки...')
            LogEntry.objects.filter(user_id=user_id).delete()
            
            # Удаляем самого пользователя
            self.stdout.write(f'Удаление пользователя {user.username}...')
            user.delete()
            
            self.stdout.write(self.style.SUCCESS(f'✅ Пользователь {email or username} и все связанные данные успешно удалены!'))
            
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Пользователь с email={email} или username={username} не найден'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка при удалении: {e}'))

