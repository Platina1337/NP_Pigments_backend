"""
Централизованная конфигурация URL-адресов для платежных систем
"""
import os
from django.conf import settings


class PaymentURLConfig:
    """Класс для централизованного управления URL-адресами платежных систем"""

    # Базовый URL фронтенда
    FRONTEND_BASE_URL = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')

    # URL для успешной оплаты (куда перенаправлять после оплаты)
    PAYMENT_SUCCESS_URL = f"{FRONTEND_BASE_URL}/payment/success"

    # URL для неудачной оплаты
    PAYMENT_FAILED_URL = f"{FRONTEND_BASE_URL}/payment/failed"

    # URL для webhook уведомлений от ЮKassa (куда ЮKassa будет отправлять уведомления)
    YOOKASSA_WEBHOOK_URL = os.getenv('YOOKASSA_WEBHOOK_URL', f"{settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'http://localhost:8000'}/api/payments/yookassa/webhook/")

    # URL для webhook уведомлений от Тинькофф
    TINKOFF_WEBHOOK_URL = os.getenv('TINKOFF_WEBHOOK_URL', f"{settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'http://localhost:8000'}/api/payments/tinkoff/webhook/")

    @classmethod
    def get_yookassa_return_url(cls, order_id: int) -> str:
        """Получить URL для возврата после оплаты через ЮKassa"""
        return f"{cls.PAYMENT_SUCCESS_URL}?order_id={order_id}"

    @classmethod
    def get_tinkoff_success_url(cls) -> str:
        """Получить URL для успешной оплаты через Тинькофф"""
        return cls.PAYMENT_SUCCESS_URL

    @classmethod
    def get_tinkoff_fail_url(cls) -> str:
        """Получить URL для неудачной оплаты через Тинькофф"""
        return cls.PAYMENT_FAILED_URL

    @classmethod
    def get_yookassa_webhook_url(cls) -> str:
        """Получить URL для webhook уведомлений ЮKassa"""
        return cls.YOOKASSA_WEBHOOK_URL

    @classmethod
    def get_tinkoff_webhook_url(cls) -> str:
        """Получить URL для webhook уведомлений Тинькофф"""
        return cls.TINKOFF_WEBHOOK_URL

    @classmethod
    def update_frontend_url(cls, new_url: str):
        """Обновить базовый URL фронтенда (для динамического изменения)"""
        cls.FRONTEND_BASE_URL = new_url.rstrip('/')
        cls.PAYMENT_SUCCESS_URL = f"{cls.FRONTEND_BASE_URL}/payment/success"
        cls.PAYMENT_FAILED_URL = f"{cls.FRONTEND_BASE_URL}/payment/failed"

    @classmethod
    def update_webhook_urls(cls, yookassa_url: str = None, tinkoff_url: str = None):
        """Обновить URL-адреса для webhook уведомлений"""
        if yookassa_url:
            cls.YOOKASSA_WEBHOOK_URL = yookassa_url
        if tinkoff_url:
            cls.TINKOFF_WEBHOOK_URL = tinkoff_url

    @classmethod
    def get_config_summary(cls) -> dict:
        """Получить сводку текущей конфигурации"""
        return {
            'frontend_base_url': cls.FRONTEND_BASE_URL,
            'payment_success_url': cls.PAYMENT_SUCCESS_URL,
            'payment_failed_url': cls.PAYMENT_FAILED_URL,
            'yookassa_webhook_url': cls.YOOKASSA_WEBHOOK_URL,
            'tinkoff_webhook_url': cls.TINKOFF_WEBHOOK_URL,
        }


# Глобальный экземпляр конфигурации
payment_urls = PaymentURLConfig()
