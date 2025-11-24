"""
Провайдер для интеграции с Тинькофф Эквайринг
Документация: https://www.tinkoff.ru/kassa/develop/api/
"""
import requests
import hashlib
from django.conf import settings


class TinkoffProvider:
    """Класс для работы с Тинькофф Эквайринг"""
    
    API_URL = 'https://securepay.tinkoff.ru/v2/'
    
    def __init__(self):
        """Инициализация конфигурации Тинькофф"""
        self.terminal_key = settings.TINKOFF_TERMINAL_KEY
        self.secret_key = settings.TINKOFF_SECRET_KEY
    
    def _generate_token(self, params):
        """
        Генерация токена для подписи запроса
        
        Args:
            params: словарь параметров запроса
            
        Returns:
            str: токен
        """
        # Добавляем секретный ключ и терминал
        token_params = {
            'Password': self.secret_key,
            'TerminalKey': self.terminal_key,
            **params
        }
        
        # Удаляем параметры, которые не участвуют в генерации токена
        exclude_keys = ['Receipt', 'DATA', 'Shops', 'Receipt']
        for key in exclude_keys:
            token_params.pop(key, None)
        
        # Сортируем по ключам и объединяем значения
        sorted_values = [str(token_params[key]) for key in sorted(token_params.keys())]
        concatenated = ''.join(sorted_values)
        
        # Хешируем SHA-256
        return hashlib.sha256(concatenated.encode()).hexdigest()
    
    def init_payment(self, order, success_url, fail_url):
        """
        Инициализация платежа в Тинькофф
        
        Args:
            order: объект заказа Order
            success_url: URL для успешной оплаты
            fail_url: URL для неудачной оплаты
            
        Returns:
            dict: данные о созданном платеже
        """
        try:
            # Подготавливаем параметры
            params = {
                'TerminalKey': self.terminal_key,
                'Amount': int(order.total * 100),  # Сумма в копейках
                'OrderId': str(order.id),
                'Description': f'Оплата заказа #{order.id}',
                'SuccessURL': success_url,
                'FailURL': fail_url,
                'DATA': {
                    'Email': order.user.email,
                    'Phone': order.delivery_phone
                }
            }
            
            # Генерируем токен
            token = self._generate_token({
                'TerminalKey': self.terminal_key,
                'Amount': params['Amount'],
                'OrderId': params['OrderId'],
                'Description': params['Description']
            })
            params['Token'] = token
            
            # Отправляем запрос
            response = requests.post(
                f'{self.API_URL}Init',
                json=params,
                timeout=10
            )
            data = response.json()
            
            if data.get('Success'):
                return {
                    'success': True,
                    'payment_id': data.get('PaymentId'),
                    'status': data.get('Status'),
                    'payment_url': data.get('PaymentURL'),
                    'payment_data': data
                }
            else:
                return {
                    'success': False,
                    'error': data.get('Message', 'Unknown error'),
                    'error_code': data.get('ErrorCode')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_payment_state(self, payment_id):
        """
        Получение статуса платежа
        
        Args:
            payment_id: ID платежа в Тинькофф
            
        Returns:
            dict: статус платежа
        """
        try:
            params = {
                'TerminalKey': self.terminal_key,
                'PaymentId': payment_id
            }
            
            token = self._generate_token(params)
            params['Token'] = token
            
            response = requests.post(
                f'{self.API_URL}GetState',
                json=params,
                timeout=10
            )
            data = response.json()
            
            if data.get('Success'):
                return {
                    'success': True,
                    'payment_id': data.get('PaymentId'),
                    'status': data.get('Status'),
                    'order_id': data.get('OrderId'),
                    'amount': data.get('Amount', 0) / 100,  # Переводим из копеек
                    'payment_data': data
                }
            else:
                return {
                    'success': False,
                    'error': data.get('Message', 'Unknown error'),
                    'error_code': data.get('ErrorCode')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def handle_notification(self, data):
        """
        Обработка уведомлений от Тинькофф
        
        Args:
            data: данные уведомления
            
        Returns:
            dict: результат обработки
        """
        try:
            # Проверяем токен уведомления
            received_token = data.pop('Token', None)
            calculated_token = self._generate_token(data)
            
            if received_token != calculated_token:
                return {
                    'success': False,
                    'error': 'Invalid token'
                }
            
            return {
                'success': True,
                'payment_id': data.get('PaymentId'),
                'status': data.get('Status'),
                'order_id': data.get('OrderId'),
                'amount': data.get('Amount', 0) / 100,
                'success_payment': data.get('Success', False)
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
            payment_id: ID платежа в Тинькофф
            
        Returns:
            dict: результат отмены
        """
        try:
            params = {
                'TerminalKey': self.terminal_key,
                'PaymentId': payment_id
            }
            
            token = self._generate_token(params)
            params['Token'] = token
            
            response = requests.post(
                f'{self.API_URL}Cancel',
                json=params,
                timeout=10
            )
            data = response.json()
            
            if data.get('Success'):
                return {
                    'success': True,
                    'payment_id': data.get('PaymentId'),
                    'status': data.get('Status'),
                    'original_amount': data.get('OriginalAmount', 0) / 100
                }
            else:
                return {
                    'success': False,
                    'error': data.get('Message', 'Unknown error'),
                    'error_code': data.get('ErrorCode')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

