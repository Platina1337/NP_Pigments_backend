from django.forms import ValidationError
from allauth.account.forms import LoginForm


class AdminLoginForm(LoginForm):
    """
    Кастомная форма логина для allauth:
    - нормальный текст ошибок (без "введите правильный email")
    - вход по email или username
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        login_field = self.fields.get("login")
        password_field = self.fields.get("password")

        if login_field:
            login_field.label = "Email или логин"
            # Человеческое сообщение при невалидном вводе
            login_field.error_messages["invalid"] = "Неверный логин или пароль."
            login_field.widget.input_type = "text"
            login_field.widget.attrs.setdefault("placeholder", "email или логин")

        if password_field:
            password_field.label = "Пароль"
            password_field.widget.attrs.setdefault("placeholder", "пароль")

    def clean(self):
        """
        Перехватываем общую ошибку и подменяем на одну понятную строку.
        """
        try:
            cleaned_data = super().clean()
        except ValidationError:
            # На всякий случай, если родитель выбросит ValidationError
            raise ValidationError("Неверный логин или пароль.")

        non_field = self._errors.get("__all__")
        if non_field:
            self._errors["__all__"] = self.error_class(["Неверный логин или пароль."])

        return cleaned_data


