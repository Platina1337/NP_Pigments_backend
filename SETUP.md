# Инструкция по запуску

## 1. Активация виртуального окружения

```powershell
cd backend
.\venv\Scripts\Activate.ps1
```

## 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

## 3. Создание миграций для новых полей

```bash
python manage.py makemigrations store
```

Эта команда создаст миграцию для новых полей в модели Order:
- payment_id
- delivery_method
- tracking_number
- delivery_service_order_id
- estimated_delivery_date

## 4. Применение миграций

```bash
python manage.py migrate
```

## 5. Создание суперпользователя (если еще не создан)

```bash
python manage.py createsuperuser
```

## 6. Запуск сервера

```bash
python manage.py runserver
```

## 7. Доступ к админ-панели

Откройте http://localhost:8000/admin и войдите с учетными данными суперпользователя.

В админ-панели теперь доступны:
- Управление брендами
- Управление категориями
- Управление парфюмами (с массовыми действиями)
- Управление пигментами
- Управление заказами (с изменением статусов)
- Просмотр корзин пользователей
- Управление профилями пользователей
- Просмотр Email OTP кодов

## Заполнение тестовыми данными

Можно загрузить тестовые данные из фикстур:

```bash
python manage.py loaddata store/fixtures/test_data.json
```

## Проверка работы

1. Откройте админ-панель: http://localhost:8000/admin
2. Добавьте несколько брендов
3. Добавьте категории
4. Добавьте товары (парфюмы)
5. Проверьте API: http://localhost:8000/api/perfumes/

