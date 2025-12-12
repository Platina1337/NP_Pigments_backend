from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


class CustomAccountAdapter(DefaultAccountAdapter):
    """Кастомный адаптер для allauth account"""

    def is_open_for_signup(self, request):
        """
        Проверяет, разрешена ли регистрация новых пользователей
        """
        # В админ-панели регистрации быть не должно
        return False


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Кастомный адаптер для allauth social account"""

    def is_open_for_signup(self, request, sociallogin):
        """
        Проверяет, разрешена ли регистрация через социальные сети
        """
        # Запрещаем социальную регистрацию
        return False

    def populate_user(self, request, sociallogin, data):
        """
        Заполняет данные пользователя из социальной сети
        ВАЖНО: Данные профиля (first_name, last_name) НЕ сохраняются в User,
        они будут сохранены в UserProfile через сигнал или отдельную логику
        """
        user = super().populate_user(request, sociallogin, data)

        # Устанавливаем только username из Google данных (данные для входа)
        if sociallogin.account.provider == 'google':
            user.username = data.get('email', '').split('@')[0]
            # НЕ сохраняем first_name и last_name в User - они хранятся только в UserProfile

        return user
