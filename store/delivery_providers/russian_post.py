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
            order_data: данные заказа
            
        Returns:
            dict: результат создания заказа
        """
        try:
            if self.test_mode or not self.token or not self.key:
                # В тестовом режиме возвращаем мок
                import random
                tracking_number = f'RP{random.randint(100000000000, 999999999999)}'
                
                return {
                    'success': True,
                    'tracking_number': tracking_number,
                    'test_mode': True
                }
            
            # Реальное создание заказа через API
            response = requests.post(
                f"{self.base_url}user/shipment",
                headers=self.headers,
                json=order_data
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'tracking_number': result.get('barcode'),
                    'order_id': result.get('order-num'),
                    'data': result
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}'
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
            if self.test_mode or not self.token or not self.key:
                # В тестовом режиме возвращаем мок
                return {
                    'success': True,
                    'status': 'В пути',
                    'location': 'Москва',
                    'test_mode': True
                }
            
            # Реальное отслеживание через API
            response = requests.get(
                f"{self.base_url}tracking",
                headers=self.headers,
                params={'track': tracking_number}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result and len(result) > 0:
                    track_info = result[0]
                    operations = track_info.get('operations', [])
                    
                    if operations:
                        last_operation = operations[-1]
                        return {
                            'success': True,
                            'status': last_operation.get('operation-type', {}).get('name', 'Неизвестно'),
                            'location': last_operation.get('address-parameters', {}).get('place', None),
                            'date': last_operation.get('operation-date'),
                            'data': track_info
                        }
            
            return {
                'success': False,
                'error': 'Tracking info not found'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

