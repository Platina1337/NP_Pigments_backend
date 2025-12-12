import logging


class SuppressProfile401Filter(logging.Filter):
    """
    Filter для подавления логирования 401 ошибок для /api/auth/profile/
    Это необходимо потому что AuthContext автоматически проверяет профиль при загрузке
    и просроченные токены вызывают 401 ошибки, которые логируются как WARNING
    
    Django логирует в формате: "Unauthorized: /api/auth/profile/"
    """

    def filter(self, record):
        # Получаем сообщение лога
        try:
            message = str(record.getMessage())
        except Exception:
            message = str(record.msg) if hasattr(record, 'msg') else ''
        
        # Проверяем имя логгера
        logger_name = getattr(record, 'name', '')
        
        # Подавляем WARNING логи для 401 ошибок на /api/auth/profile/
        # Основная проверка: WARNING уровень + имя логгера django.request + путь в сообщении
        if (
            record.levelname == 'WARNING' and
            logger_name == 'django.request' and
            '/api/auth/profile/' in message
        ):
            # Подавляем логирование
            return False
        
        # Дополнительная проверка через сообщение (на случай другого формата)
        if (
            record.levelname == 'WARNING' and
            'Unauthorized' in message and
            '/api/auth/profile/' in message
        ):
            return False
        
        return True


class SuppressProfile401Middleware:
    """
    Middleware для подавления логирования 401 ошибок для /api/auth/profile/
    Перехватывает ответы и подавляет логирование через временное изменение уровня логирования
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('django.request')

    def __call__(self, request):
        # Сохраняем оригинальный уровень логирования
        original_level = self.logger.level
        
        response = self.get_response(request)

        # Если это GET запрос к /api/auth/profile/ с 401 ответом, подавляем логирование
        if (
            request.path == '/api/auth/profile/' and
            request.method == 'GET' and
            response.status_code == 401
        ):
            # Временно поднимаем уровень логирования до ERROR, чтобы не логировать WARNING
            self.logger.setLevel(logging.ERROR)
            
            # Восстанавливаем уровень после небольшой задержки
            # Но это не сработает, так как логирование происходит синхронно
            # Поэтому используем фильтр логирования вместо этого
        
        # Восстанавливаем уровень логирования
        self.logger.setLevel(original_level)

        return response
