#!/usr/bin/env python
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'perfume_store.settings')
django.setup()

from adminpanel.forms import UserForm
from django.contrib.auth.models import User
from store.models import UserProfile

def test_save():
    # Получаем пользователя
    user = User.objects.get(id=6)  # Пользователь с ID 6
    profile, _ = UserProfile.objects.get_or_create(user=user)

    print(f"Before save - user: {user.username}, profile: first_name='{profile.first_name}', last_name='{profile.last_name}'")

    # Тестовые данные
    test_data = {
        'username': user.username,
        'email': user.email,
        'first_name': 'ТестовоеИмя',
        'last_name': 'ТестоваяФамилия',
        'is_active': user.is_active,
        'is_staff': user.is_staff
    }

    # Создаем форму
    form = UserForm(test_data, instance=user)
    print(f"Form valid: {form.is_valid()}")
    if not form.is_valid():
        print(f"Form errors: {form.errors}")
        return

    # Сохраняем
    form.save()

    # Проверяем результат
    user.refresh_from_db()
    profile.refresh_from_db()
    print(f"After save - user: {user.username}, profile: first_name='{profile.first_name}', last_name='{profile.last_name}'")

if __name__ == '__main__':
    test_save()
