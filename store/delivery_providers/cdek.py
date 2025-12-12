"""
Провайдер для интеграции с CDEK
Документация: https://api-docs.cdek.ru/
"""
import requests
from django.conf import settings
from datetime import datetime, timedelta


class CDEKProvider:
    """Класс для работы со службой доставки CDEK"""
    
    # API URL в зависимости от тестового режима
    TEST_API_URL = 'https://api.edu.cdek.ru/v2/'
    PROD_API_URL = 'https://api.cdek.ru/v2/'
    
    def __init__(self):
        """Инициализация конфигурации CDEK"""
        self.account = settings.CDEK_ACCOUNT
        self.secret_key = settings.CDEK_SECRET_KEY
        self.test_mode = getattr(settings, 'CDEK_TEST_MODE', True)
        self.api_url = self.TEST_API_URL if self.test_mode else self.PROD_API_URL
        self.token = None
        self.token_expires = None
    
    def _get_token(self):
        """Получение токена авторизации"""
        # Проверяем, не истек ли текущий токен
        if self.token and self.token_expires and datetime.now() < self.token_expires:
            return self.token
        
        try:
            response = requests.post(
                f'{self.api_url}oauth/token',
                params={
                    'grant_type': 'client_credentials',
                    'client_id': self.account,
                    'client_secret': self.secret_key
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('access_token')
                # Токен истекает через expires_in секунд (минус небольшой запас)
                expires_in = data.get('expires_in', 3600) - 60
                self.token_expires = datetime.now() + timedelta(seconds=expires_in)
                return self.token
            else:
                raise Exception(f'Failed to get CDEK token: {response.text}')
                
        except Exception as e:
            raise Exception(f'CDEK auth error: {str(e)}')
    
    def _make_request(self, method, endpoint, data=None, params=None):
        """Выполнение запроса к API CDEK"""
        token = self._get_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        url = f'{self.api_url}{endpoint}'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=10)
            else:
                raise ValueError(f'Unsupported method: {method}')
            
            return response
            
        except Exception as e:
            raise Exception(f'CDEK API request error: {str(e)}')
    
    def calculate_delivery(self, from_postal_code, to_postal_code, packages):
        """
        Расчет стоимости доставки
        
        Args:
            from_postal_code: индекс отправителя
            to_postal_code: индекс получателя
            packages: список посылок с характеристиками [{'weight': 500, 'length': 10, 'width': 10, 'height': 10}]
            
        Returns:
            dict: данные о доставке
        """
        try:
            # Тарифы CDEK (примеры)
            # 136 - Посылка склад-склад
            # 137 - Посылка склад-дверь
            # 138 - Посылка дверь-склад
            # 139 - Посылка дверь-дверь
            tariff_codes = [137, 139]  # склад-дверь и дверь-дверь
            
            results = []
            
            for tariff_code in tariff_codes:
                data = {
                    'type': 1,  # Интернет-магазин
                    'currency': 1,  # Рубли
                    'tariff_code': tariff_code,
                    'from_location': {
                        'postal_code': from_postal_code
                    },
                    'to_location': {
                        'postal_code': to_postal_code
                    },
                    'packages': packages
                }
                
                response = self._make_request('POST', 'calculator/tariff', data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    results.append({
                        'tariff_code': tariff_code,
                        'tariff_name': self._get_tariff_name(tariff_code),
                        'delivery_sum': result.get('delivery_sum', 0),
                        'period_min': result.get('period_min', 0),
                        'period_max': result.get('period_max', 0),
                        'currency': 'RUB'
                    })
            
            if results:
                return {
                    'success': True,
                    'options': results
                }
            else:
                return {
                    'success': False,
                    'error': 'No delivery options available'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_tariff_name(self, tariff_code):
        """Получение названия тарифа"""
        tariffs = {
            136: 'Посылка склад-склад',
            137: 'Посылка склад-дверь',
            138: 'Посылка дверь-склад',
            139: 'Посылка дверь-дверь',
        }
        return tariffs.get(tariff_code, f'Тариф {tariff_code}')
    
    def create_order(self, order_data):
        """
        Создание заказа на доставку
        
        Args:
            order_data: данные заказа в формате CDEK API
            
        Returns:
            dict: результат создания заказа
        """
        try:
            # Проверяем наличие учетных данных
            if not self.account or not self.secret_key:
                return {
                    'success': False,
                    'error': 'CDEK credentials not configured. Set CDEK_ACCOUNT and CDEK_SECRET_KEY in settings.'
                }
            
            response = self._make_request('POST', 'orders', data=order_data)
            
            if response.status_code in [200, 201]:
                result = response.json()
                entity = result.get('entity', {})
                
                return {
                    'success': True,
                    'order_uuid': entity.get('uuid'),
                    'cdek_number': entity.get('cdek_number'),
                    'request_uuid': result.get('request_uuid'),
                    'data': result
                }
            else:
                try:
                    error_data = response.json()
                    error_message = 'Unknown error'
                    if 'errors' in error_data and len(error_data['errors']) > 0:
                        error_message = error_data['errors'][0].get('message', 'Unknown error')
                    elif 'error' in error_data:
                        error_message = error_data['error']
                    elif 'message' in error_data:
                        error_message = error_data['message']
                    
                    return {
                        'success': False,
                        'error': error_message,
                        'status_code': response.status_code,
                        'response': error_data
                    }
                except:
                    return {
                        'success': False,
                        'error': f'API error: {response.status_code} - {response.text[:200]}',
                        'status_code': response.status_code
                    }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_tracking_info(self, cdek_number):
        """
        Получение информации об отслеживании
        
        Args:
            cdek_number: номер отправления CDEK
            
        Returns:
            dict: информация об отслеживании
        """
        try:
            # Проверяем наличие учетных данных
            if not self.account or not self.secret_key:
                return {
                    'success': False,
                    'error': 'CDEK credentials not configured'
                }
            
            # Используем правильный формат запроса для получения заказа по номеру
            response = self._make_request(
                'GET', 
                f'orders/{cdek_number}'
            )
            
            if response.status_code == 200:
                result = response.json()
                entity = result.get('entity', {})
                
                if entity:
                    statuses = entity.get('statuses', [])
                    last_status = statuses[-1] if statuses else {}
                    
                    return {
                        'success': True,
                        'status': last_status.get('name', 'Неизвестно'),
                        'status_code': last_status.get('code'),
                        'location': last_status.get('city'),
                        'date': last_status.get('date_time'),
                        'cdek_number': entity.get('cdek_number'),
                        'order_uuid': entity.get('uuid'),
                        'all_statuses': statuses,
                        'data': entity
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Order not found in response'
                    }
            else:
                try:
                    error_data = response.json()
                    return {
                        'success': False,
                        'error': error_data.get('message', f'API error: {response.status_code}'),
                        'status_code': response.status_code
                    }
                except:
                    return {
                        'success': False,
                        'error': f'API error: {response.status_code}',
                        'status_code': response.status_code
                    }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

