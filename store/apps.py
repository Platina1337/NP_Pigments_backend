from django.apps import AppConfig
from django.utils.log import log_response as original_log_response


def custom_log_response(status_code, response, request, *args, **kwargs):
    """
    Кастомная функция логирования, которая подавляет 401 ошибки для /api/auth/profile/
    """
    # Если это 401 ошибка для GET запроса к /api/auth/profile/, не логируем
    if (
        status_code == 401 and
        hasattr(request, 'path') and
        request.path == '/api/auth/profile/' and
        hasattr(request, 'method') and
        request.method == 'GET'
    ):
        return  # Подавляем логирование
    
    # Для всех остальных случаев используем оригинальную функцию
    return original_log_response(status_code, response, request, *args, **kwargs)


class StoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'

    def ready(self):
        # Применяем monkey-patching для подавления логирования 401 ошибок
        import django.utils.log
        django.utils.log.log_response = custom_log_response
