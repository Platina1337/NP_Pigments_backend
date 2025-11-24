from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


class CustomAccountAdapter(DefaultAccountAdapter):
    """Кастомный адаптер для allauth account"""

    def is_open_for_signup(self, request):
        """
        Проверяет, разрешена ли регистрация новых пользователей
        """
        return True


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Кастомный адаптер для allauth social account"""

    def is_open_for_signup(self, request, sociallogin):
        """
        Проверяет, разрешена ли регистрация через социальные сети
        """
        return True

    def populate_user(self, request, sociallogin, data):
        """
        Заполняет данные пользователя из социальной сети
        """
        user = super().populate_user(request, sociallogin, data)

        # Устанавливаем имя пользователя из Google данных
        if sociallogin.account.provider == 'google':
            user.first_name = data.get('given_name', '')
            user.last_name = data.get('family_name', '')
            user.username = data.get('email', '').split('@')[0]

        return user
