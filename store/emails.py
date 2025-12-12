"""
Модуль для отправки email уведомлений
"""
import secrets
import string
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


def send_otp_email(email, otp_code, purpose='login', magic_token=None):
    """
    Отправка OTP кода на email с магической ссылкой
    
    Args:
        email: email получателя
        otp_code: OTP код
        purpose: цель (login/register)
        magic_token: токен для магической ссылки
    """
    purpose_text = 'входа' if purpose == 'login' else 'регистрации'
    subject = f'Код подтверждения для {purpose_text} — NP Perfumes'
    
    # Получаем URL фронтенда из настроек или используем дефолтный
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    
    # Формируем магическую ссылку
    magic_link = ""
    if magic_token:
        magic_link = f"{frontend_url}/auth/magic?token={magic_token}&purpose={purpose}"
    
    # HTML версия письма
    html_message = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Код подтверждения</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f5f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 100%; max-width: 480px; border-collapse: collapse; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 32px; text-align: center; border-bottom: 1px solid #f0f0f0;">
                            <div style="display: inline-block; background-color: #2a5c5c; color: #ffffff; font-family: Georgia, serif; font-weight: bold; font-size: 24px; padding: 12px 20px; border-radius: 12px;">
                                NP
                            </div>
                            <h1 style="margin: 16px 0 0; font-size: 24px; font-weight: 600; color: #1a1a1a;">
                                NP Perfumes
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px 40px;">
                            <p style="margin: 0 0 24px; font-size: 16px; color: #4a4a4a; line-height: 1.6;">
                                Здравствуйте! Вот ваш код подтверждения для {purpose_text}:
                            </p>
                            
                            <!-- OTP Code -->
                            <div style="background: linear-gradient(135deg, #2a5c5c 0%, #3a7a7a 100%); border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 24px;">
                                <span style="font-family: 'Courier New', monospace; font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #ffffff;">
                                    {otp_code}
                                </span>
                            </div>
                            
                            <p style="margin: 0 0 8px; font-size: 14px; color: #888888; text-align: center;">
                                Код действителен 10 минут
                            </p>
                            
                            {f'''
                            <!-- Divider -->
                            <div style="margin: 32px 0; text-align: center;">
                                <span style="display: inline-block; padding: 0 16px; background: #fff; color: #888; font-size: 13px;">
                                    или
                                </span>
                            </div>
                            
                            <!-- Magic Link -->
                            <p style="margin: 0 0 16px; font-size: 15px; color: #4a4a4a; text-align: center;">
                                Нажмите на кнопку для мгновенного входа:
                            </p>
                            
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td align="center">
                                        <a href="{magic_link}" style="display: inline-block; background: linear-gradient(135deg, #2a5c5c 0%, #3a7a7a 100%); color: #ffffff; text-decoration: none; padding: 16px 48px; border-radius: 50px; font-size: 16px; font-weight: 600; box-shadow: 0 4px 16px rgba(42, 92, 92, 0.3);">
                                            ✨ Войти мгновенно
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="margin: 24px 0 0; font-size: 12px; color: #aaa; text-align: center;">
                                Или скопируйте ссылку:<br>
                                <a href="{magic_link}" style="color: #2a5c5c; word-break: break-all;">{magic_link}</a>
                            </p>
                            ''' if magic_token else ''}
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px 32px; border-top: 1px solid #f0f0f0; text-align: center;">
                            <p style="margin: 0; font-size: 13px; color: #888888; line-height: 1.5;">
                                Если вы не запрашивали этот код,<br>просто проигнорируйте это письмо.
                            </p>
                            <p style="margin: 16px 0 0; font-size: 12px; color: #aaaaaa;">
                                © 2025 NP Perfumes. Все права защищены.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    
    # Текстовая версия письма
    message = f"""
Код подтверждения для {purpose_text}: {otp_code}

Код действителен в течение 10 минут.
{'Или используйте магическую ссылку для мгновенного входа: ' + magic_link if magic_token else ''}

Если вы не запрашивали этот код, просто проигнорируйте это письмо.

С уважением,
Команда NP Perfumes
"""
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
            html_message=html_message,
        )
        return True
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return False


def generate_random_password(length=12):
    """
    Генерирует случайный безопасный пароль
    
    Args:
        length: длина пароля (по умолчанию 12 символов)
    
    Returns:
        str: случайный пароль
    """
    # Используем буквы (верхний и нижний регистр), цифры и специальные символы
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def send_google_password_email(email, password, username, name=''):
    """
    Отправка пароля на email после регистрации через Google
    
    Args:
        email: email получателя
        password: сгенерированный пароль
        username: имя пользователя
        name: имя пользователя (опционально)
    """
    subject = 'Добро пожаловать в NP Perfumes — Ваш пароль для входа'
    
    # HTML версия письма
    html_message = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Добро пожаловать в NP Perfumes</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 40px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #3B7171 0%, #2A4A4A 100%); padding: 40px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">Добро пожаловать в NP Perfumes!</h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; color: #333333; line-height: 1.6;">
                                {'Здравствуйте, ' + name + '!' if name else 'Здравствуйте!'}
                            </p>
                            
                            <p style="margin: 0 0 20px; font-size: 16px; color: #333333; line-height: 1.6;">
                                Вы успешно зарегистрировались через Google аккаунт. Для вашего удобства мы создали пароль, который вы можете использовать для входа через логин и пароль.
                            </p>
                            
                            <div style="background-color: #f8f9fa; border-left: 4px solid #3B7171; padding: 20px; margin: 30px 0; border-radius: 4px;">
                                <p style="margin: 0 0 10px; font-size: 14px; color: #666666; font-weight: 600;">Ваши данные для входа:</p>
                                <p style="margin: 5px 0; font-size: 14px; color: #333333;">
                                    <strong>Логин:</strong> {username}
                                </p>
                                <p style="margin: 5px 0; font-size: 14px; color: #333333;">
                                    <strong>Email:</strong> {email}
                                </p>
                                <p style="margin: 10px 0 5px; font-size: 14px; color: #333333;">
                                    <strong>Пароль:</strong>
                                </p>
                                <div style="background-color: #ffffff; border: 2px solid #3B7171; border-radius: 4px; padding: 12px; margin-top: 8px;">
                                    <code style="font-size: 18px; font-weight: 600; color: #3B7171; letter-spacing: 2px; font-family: 'Courier New', monospace;">{password}</code>
                                </div>
                            </div>
                            
                            <p style="margin: 20px 0; font-size: 14px; color: #666666; line-height: 1.6;">
                                <strong>Важно:</strong> Сохраните этот пароль в безопасном месте. Вы можете использовать его для входа на сайт вместе с вашим логином или email.
                            </p>
                            
                            <p style="margin: 20px 0; font-size: 14px; color: #666666; line-height: 1.6;">
                                Вы также можете продолжить использовать вход через Google — оба способа работают одинаково хорошо.
                            </p>
                            
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')}/login" 
                                   style="display: inline-block; background: linear-gradient(135deg, #3B7171 0%, #2A4A4A 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                    Войти в аккаунт
                                </a>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px 32px; border-top: 1px solid #f0f0f0; text-align: center;">
                            <p style="margin: 0; font-size: 13px; color: #888888; line-height: 1.5;">
                                Если вы не регистрировались через Google,<br>проигнорируйте это письмо.
                            </p>
                            <p style="margin: 16px 0 0; font-size: 12px; color: #aaaaaa;">
                                © 2025 NP Perfumes. Все права защищены.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    
    # Текстовая версия письма
    message = f"""
Добро пожаловать в NP Perfumes!

{'Здравствуйте, ' + name + '!' if name else 'Здравствуйте!'}

Вы успешно зарегистрировались через Google аккаунт. Для вашего удобства мы создали пароль, который вы можете использовать для входа через логин и пароль.

Ваши данные для входа:
Логин: {username}
Email: {email}
Пароль: {password}

Важно: Сохраните этот пароль в безопасном месте. Вы можете использовать его для входа на сайт вместе с вашим логином или email.

Вы также можете продолжить использовать вход через Google — оба способа работают одинаково хорошо.

С уважением,
Команда NP Perfumes
"""
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
            html_message=html_message,
        )
        return True
    except Exception as e:
        print(f"Error sending Google password email: {e}")
        return False

