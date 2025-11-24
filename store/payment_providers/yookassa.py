"""
Провайдер для интеграции с ЮKassa
Документация: https://yookassa.ru/developers/api
"""
from yookassa import Configuration, Payment
from django.conf import settings
import uuid


class YooKassaProvider:
    """Класс для работы с платежной системой ЮKassa"""
    
    def __init__(self):
        """Инициализация конфигурации ЮKassa"""
        Configuration.account_id = settings.YOOKASSA_SHOP_ID
        Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    
    def create_payment(self, order, return_url):
        """
        Создание платежа в ЮKassa
        
        Args:
            order: объект заказа Order
            return_url: URL для возврата после оплаты
            
        Returns:
            dict: данные о созданном платеже
        """
        try:
            # Генерируем уникальный idempotence key для безопасности
            idempotence_key = str(uuid.uuid4())
            
            # Создаем платеж
            payment = Payment.create({
                "amount": {
                    "value": str(order.total),
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url
                },
                "capture": True,  # Автоматическое списание
                "description": f"Оплата заказа #{order.id}",
                "metadata": {
                    "order_id": order.id,
                    "user_id": order.user.id
                }
            }, idempotence_key)
            
            return {
                'success': True,
                'payment_id': payment.id,
                'status': payment.status,
                'confirmation_url': payment.confirmation.confirmation_url if payment.confirmation else None,
                'payment_data': payment
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_payment_status(self, payment_id):
        """
        Проверка статуса платежа
        
        Args:
            payment_id: ID платежа в ЮKassa
            
        Returns:
            dict: статус платежа
        """
        try:
            payment = Payment.find_one(payment_id)
            
            return {
                'success': True,
                'payment_id': payment.id,
                'status': payment.status,
                'paid': payment.paid,
                'amount': float(payment.amount.value) if payment.amount else 0,
                'payment_data': payment
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def handle_webhook(self, data):
        """
        Обработка webhook уведомлений от ЮKassa
        
        Args:
            data: данные webhook запроса
            
        Returns:
            dict: результат обработки
        """
        try:
            event = data.get('event')
            payment_obj = data.get('object')
            
            if not payment_obj:
                return {'success': False, 'error': 'No payment object in webhook'}
            
            payment_id = payment_obj.get('id')
            status = payment_obj.get('status')
            metadata = payment_obj.get('metadata', {})
            order_id = metadata.get('order_id')
            
            return {
                'success': True,
                'event': event,
                'payment_id': payment_id,
                'status': status,
                'order_id': order_id,
                'paid': payment_obj.get('paid', False),
                'amount': float(payment_obj.get('amount', {}).get('value', 0))
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_payment(self, payment_id):
        """
        Отмена платежа
        
        Args:
            payment_id: ID платежа в ЮKassa
            
        Returns:
            dict: результат отмены
        """
        try:
            payment = Payment.cancel(payment_id, str(uuid.uuid4()))
            
            return {
                'success': True,
                'payment_id': payment.id,
                'status': payment.status
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

