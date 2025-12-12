"""
Провайдер для интеграции с Почтой России
Документация: https://otpravka.pochta.ru/specification
"""
import requests
from django.conf import settings


class RussianPostProvider:
    """Класс для работы с Почтой России"""
    
    def __init__(self):
        """Инициализация конфигурации Почты России"""
        # Используем тестовый режим, если не указаны реальные ключи
        self.test_mode = getattr(settings, 'RUSSIAN_POST_TEST_MODE', True)
        self.token = getattr(settings, 'RUSSIAN_POST_TOKEN', '')
        self.key = getattr(settings, 'RUSSIAN_POST_KEY', '')
        
        # Базовые настройки для API
        self.base_url = "https://otpravka.pochta.ru/1.0/"
        self.headers = {
            'Authorization': f'AccessToken {self.token}',
            'X-User-Authorization': f'Basic {self.key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def calculate_delivery(self, from_postal_code, to_postal_code, weight_grams):
        """
        Расчет стоимости доставки
        
        Args:
            from_postal_code: индекс отправителя
            to_postal_code: индекс получателя
            weight_grams: вес в граммах
            
        Returns:
            dict: данные о доставке
        """
        try:
            if self.test_mode or not self.token or not self.key:
                # Упрощенный расчет для тестового режима
                base_cost = 300
                weight_cost = (weight_grams / 1000) * 50  # 50 руб за кг
                total_cost = base_cost + weight_cost
                
                return {
                    'success': True,
                    'options': [{
                        'service': 'russian_post_parcel',
                        'service_name': 'Посылка 1 класса',
                        'delivery_sum': round(total_cost, 2),
                        'period_min': 3,
                        'period_max': 7,
                        'currency': 'RUB'
                    }, {
                        'service': 'russian_post_ems',
                        'service_name': 'EMS',
                        'delivery_sum': round(total_cost * 1.5, 2),
                        'period_min': 1,
                        'period_max': 3,
                        'currency': 'RUB'
                    }]
                }
            
            # Реальный расчет через API
            data = {
                "object": 270,  # Посылка онлайн
                "from-index": from_postal_code,
                "to-index": to_postal_code,
                "mass": weight_grams,
                "dimension": {
                    "height": 10,
                    "length": 20,
                    "width": 15
                }
            }
            
            response = requests.post(
                f"{self.base_url}tariff",
                headers=self.headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                options = []
                
                if isinstance(result, list):
                    for item in result:
                        options.append({
                            'service': item.get('mail-category'),
                            'service_name': item.get('mail-category-name'),
                            'delivery_sum': item.get('total-cost', 0) / 100,
                            'period_min': item.get('delivery-time', {}).get('min', 3),
                            'period_max': item.get('delivery-time', {}).get('max', 7),
                            'currency': 'RUB'
                        })
                
                return {
                    'success': True,
                    'options': options if options else [{
                        'service': 'russian_post_parcel',
                        'service_name': 'Посылка',
                        'delivery_sum': 350,
                        'period_min': 3,
                        'period_max': 7,
                        'currency': 'RUB'
                    }]
                }
            else:
                # Если API недоступен, возвращаем базовый расчет
                return {
                    'success': True,
                    'options': [{
                        'service': 'russian_post_parcel',
                        'service_name': 'Посылка (примерный расчет)',
                        'delivery_sum': 350,
                        'period_min': 3,
                        'period_max': 7,
                        'currency': 'RUB'
                    }],
                    'warning': f'Использован примерный расчет: {response.status_code}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_order(self, order_data):
        """
        Создание заказа на доставку
        
        Args:
            order_data: данные заказа в формате Почты России API
            
        Returns:
            dict: результат создания заказа
        """
        try:
            # Проверяем наличие учетных данных
            if not self.token or not self.key:
                return {
                    'success': False,
                    'error': 'Russian Post credentials not configured. Set RUSSIAN_POST_TOKEN and RUSSIAN_POST_KEY in settings.'
                }
            
            # Реальное создание заказа через API
            response = requests.post(
                f"{self.base_url}user/shipment",
                headers=self.headers,
                json=order_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                # API может вернуть массив или объект
                if isinstance(result, list) and len(result) > 0:
                    shipment = result[0]
                    return {
                        'success': True,
                        'tracking_number': shipment.get('barcode'),
                        'order_id': shipment.get('order-num'),
                        'batch_name': shipment.get('batch-name'),
                        'data': shipment
                    }
                elif isinstance(result, dict):
                    return {
                        'success': True,
                        'tracking_number': result.get('barcode'),
                        'order_id': result.get('order-num'),
                        'batch_name': result.get('batch-name'),
                        'data': result
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Unexpected response format from API'
                    }
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get('desc', f'API error: {response.status_code}')
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
    
    def get_tracking_info(self, tracking_number):
        """
        Получение информации об отслеживании
        
        Args:
            tracking_number: трек-номер отправления
            
        Returns:
            dict: информация об отслеживании
        """
        try:
            # Проверяем наличие учетных данных
            if not self.token or not self.key:
                return {
                    'success': False,
                    'error': 'Russian Post credentials not configured'
                }
            
            # Реальное отслеживание через API
            # Используем публичный API для отслеживания (не требует авторизации)
            # Или API с авторизацией если есть доступ
            tracking_url = f"{self.base_url}tracking"
            
            # Пробуем сначала с авторизацией
            response = requests.get(
                tracking_url,
                headers=self.headers,
                params={'track': tracking_number},
                timeout=30
            )
            
            # Если не получилось с авторизацией, пробуем публичный API
            if response.status_code == 401 or response.status_code == 403:
                # Используем публичный API Почты России
                public_response = requests.get(
                    f"https://www.pochta.ru/tracking",
                    params={'p': tracking_number},
                    timeout=30
                )
                # Публичный API возвращает HTML, поэтому лучше использовать API с авторизацией
                # или парсить HTML (но это сложнее)
                return {
                    'success': False,
                    'error': 'Tracking requires valid API credentials. Use public tracking at https://www.pochta.ru/tracking',
                    'public_url': f'https://www.pochta.ru/tracking?p={tracking_number}'
                }
            
            if response.status_code == 200:
                result = response.json()
                
                if result and len(result) > 0:
                    track_info = result[0]
                    operations = track_info.get('operations', [])
                    
                    if operations:
                        last_operation = operations[-1]
                        operation_type = last_operation.get('operation-type', {})
                        address_params = last_operation.get('address-parameters', {})
                        
                        return {
                            'success': True,
                            'status': operation_type.get('name', 'Неизвестно'),
                            'status_code': operation_type.get('code'),
                            'location': address_params.get('place'),
                            'index': address_params.get('index'),
                            'date': last_operation.get('operation-date'),
                            'all_operations': operations,
                            'data': track_info
                        }
                    else:
                        return {
                            'success': True,
                            'status': 'Заказ создан',
                            'data': track_info
                        }
            
            return {
                'success': False,
                'error': f'Tracking info not found. Status: {response.status_code}',
                'status_code': response.status_code
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

