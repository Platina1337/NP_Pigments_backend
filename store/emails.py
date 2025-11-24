"""
Модуль для отправки email уведомлений
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings


def send_order_confirmation(order):
    """
    Отправка подтверждения заказа
    
    Args:
        order: объект заказа Order
    """
    subject = f'Подтверждение заказа #{order.id}'
    
    # Формируем контекст для шаблона
    context = {
        'order': order,
        'items': order.items.all(),
        'user': order.user,
    }
    
    # Пока используем простой текстовый формат
    # В будущем можно создать HTML шаблоны
    message = f"""
Здравствуйте, {order.user.first_name or order.user.username}!

Спасибо за ваш заказ в нашем магазине парфюмерии.

Детали заказа:
Номер заказа: #{order.id}
Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}
Статус: {order.get_status_display()}

Адрес доставки:
{order.delivery_address}
{order.delivery_city}, {order.delivery_postal_code}
Телефон: {order.delivery_phone}

Сумма заказа: {order.subtotal} ₽
Доставка: {order.delivery_cost} ₽
Итого: {order.total} ₽

Товары:
"""
    
    for item in order.items.all():
        message += f"- {item.product_name} x {item.quantity} = {item.total_price} ₽\n"
    
    message += """

С уважением,
Команда магазина парфюмерии
"""
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending order confirmation email: {e}")
        return False


def send_payment_confirmation(order):
    """
    Отправка подтверждения оплаты
    
    Args:
        order: объект заказа Order
    """
    subject = f'Оплата заказа #{order.id} получена'
    
    message = f"""
Здравствуйте, {order.user.first_name or order.user.username}!

Ваша оплата успешно получена!

Номер заказа: #{order.id}
Сумма: {order.total} ₽
Дата оплаты: {order.paid_at.strftime('%d.%m.%Y %H:%M') if order.paid_at else 'Н/Д'}

Ваш заказ находится в обработке и скоро будет отправлен.

С уважением,
Команда магазина парфюмерии
"""
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending payment confirmation email: {e}")
        return False


def send_shipping_notification(order, tracking_number):
    """
    Отправка уведомления об отправке
    
    Args:
        order: объект заказа Order
        tracking_number: трек-номер отправления
    """
    subject = f'Заказ #{order.id} отправлен'
    
    delivery_method_name = order.get_delivery_method_display() if order.delivery_method else 'служба доставки'
    
    message = f"""
Здравствуйте, {order.user.first_name or order.user.username}!

Ваш заказ #{order.id} отправлен!

Способ доставки: {delivery_method_name}
Трек-номер: {tracking_number}
Ожидаемая дата доставки: {order.estimated_delivery_date.strftime('%d.%m.%Y') if order.estimated_delivery_date else 'уточняется'}

Вы можете отследить ваш заказ по трек-номеру на сайте службы доставки.

Адрес доставки:
{order.delivery_address}
{order.delivery_city}, {order.delivery_postal_code}

С уважением,
Команда магазина парфюмерии
"""
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending shipping notification email: {e}")
        return False


def send_delivery_notification(order):
    """
    Отправка уведомления о доставке
    
    Args:
        order: объект заказа Order
    """
    subject = f'Заказ #{order.id} доставлен'
    
    message = f"""
Здравствуйте, {order.user.first_name or order.user.username}!

Ваш заказ #{order.id} успешно доставлен!

Дата доставки: {order.delivered_at.strftime('%d.%m.%Y %H:%M') if order.delivered_at else 'Н/Д'}

Спасибо за покупку! Надеемся увидеть вас снова.

Если у вас есть вопросы или замечания, пожалуйста, свяжитесь с нами.

С уважением,
Команда магазина парфюмерии
"""
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending delivery notification email: {e}")
        return False


def send_otp_email(email, otp_code, purpose='login'):
    """
    Отправка OTP кода на email
    
    Args:
        email: email получателя
        otp_code: OTP код
        purpose: цель (login/register)
    """
    purpose_text = 'входа' if purpose == 'login' else 'регистрации'
    subject = f'Код подтверждения для {purpose_text}'
    
    message = f"""
Ваш код подтверждения: {otp_code}

Код действителен в течение 10 минут.

Если вы не запрашивали этот код, просто проигнорируйте это письмо.

С уважением,
Команда магазина парфюмерии
"""
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return False

