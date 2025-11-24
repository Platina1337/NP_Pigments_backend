from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import random
import string

class Brand(models.Model):
    """Модель бренда"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Название бренда")
    description = models.TextField(blank=True, verbose_name="Описание")
    country = models.CharField(max_length=100, blank=True, verbose_name="Страна")
    logo = models.ImageField(upload_to='brands/', blank=True, null=True, verbose_name="Логотип")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Бренд"
        verbose_name_plural = "Бренды"
        ordering = ['name']

    def __str__(self):
        return self.name

class Category(models.Model):
    """Модель категории"""
    CATEGORY_TYPES = [
        ('perfume', 'Парфюмерия'),
        ('pigment', 'Пигменты'),
    ]

    name = models.CharField(max_length=100, unique=True, verbose_name="Название категории")
    description = models.TextField(blank=True, verbose_name="Описание")
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, default='perfume', verbose_name="Тип категории")
    icon = models.CharField(max_length=50, blank=True, verbose_name="Иконка")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ['category_type', 'name']

    def __str__(self):
        return self.name

class Perfume(models.Model):
    """Модель парфюма"""
    GENDER_CHOICES = [
        ('M', 'Мужской'),
        ('F', 'Женский'),
        ('U', 'Унисекс'),
    ]

    name = models.CharField(max_length=200, verbose_name="Название")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, verbose_name="Бренд")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name="Категория",
                                limit_choices_to={'category_type': 'perfume'})
    description = models.TextField(blank=True, verbose_name="Описание")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='U', verbose_name="Пол")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Цена")
    volume_ml = models.PositiveIntegerField(verbose_name="Объем (мл)")
    concentration = models.CharField(max_length=50, blank=True, verbose_name="Концентрация")
    top_notes = models.TextField(blank=True, verbose_name="Верхние ноты")
    heart_notes = models.TextField(blank=True, verbose_name="Средние ноты")
    base_notes = models.TextField(blank=True, verbose_name="Базовые ноты")
    image = models.ImageField(upload_to='perfumes/', blank=True, null=True, verbose_name="Изображение")
    in_stock = models.BooleanField(default=True, verbose_name="В наличии")
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    featured = models.BooleanField(default=False, verbose_name="Рекомендуемый")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Парфюм"
        verbose_name_plural = "Парфюмы"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.brand.name} - {self.name}"

class Pigment(models.Model):
    """Модель пигмента"""
    COLOR_TYPES = [
        ('powder', 'Порошок'),
        ('liquid', 'Жидкий'),
        ('paste', 'Паста'),
    ]

    APPLICATION_TYPES = [
        ('cosmetics', 'Косметика'),
        ('art', 'Искусство'),
        ('industrial', 'Промышленность'),
        ('food', 'Пищевая'),
    ]

    name = models.CharField(max_length=200, verbose_name="Название")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, verbose_name="Бренд")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name="Категория",
                                limit_choices_to={'category_type': 'pigment'})
    description = models.TextField(blank=True, verbose_name="Описание")
    color_code = models.CharField(max_length=20, blank=True, verbose_name="Код цвета")
    color_type = models.CharField(max_length=20, choices=COLOR_TYPES, default='powder', verbose_name="Тип цвета")
    application_type = models.CharField(max_length=20, choices=APPLICATION_TYPES, default='cosmetics', verbose_name="Применение")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Цена")
    weight_gr = models.PositiveIntegerField(verbose_name="Вес (г)")
    image = models.ImageField(upload_to='pigments/', blank=True, null=True, verbose_name="Изображение")
    in_stock = models.BooleanField(default=True, verbose_name="В наличии")
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    featured = models.BooleanField(default=False, verbose_name="Рекомендуемый")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Пигмент"
        verbose_name_plural = "Пигменты"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.brand.name} - {self.name}"

class EmailOTP(models.Model):
    """Модель для одноразовых кодов подтверждения по email"""
    email = models.EmailField(verbose_name="Email")
    otp_code = models.CharField(max_length=6, verbose_name="OTP код")
    purpose = models.CharField(max_length=20, choices=[
        ('login', 'Вход'),
        ('register', 'Регистрация'),
    ], default='login', verbose_name="Цель")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name="Истекает")
    is_used = models.BooleanField(default=False, verbose_name="Использован")

    class Meta:
        verbose_name = "Email OTP"
        verbose_name_plural = "Email OTP коды"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} - {self.otp_code}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @staticmethod
    def generate_otp():
        """Генерирует 6-значный OTP код"""
        return ''.join(random.choices(string.digits, k=6))

    @classmethod
    def create_otp(cls, email, purpose='login'):
        """Создает новый OTP код"""
        # Удаляем старые неиспользованные коды для этого email
        cls.objects.filter(
            email=email,
            purpose=purpose,
            is_used=False
        ).delete()

        # Создаем новый код
        otp_code = cls.generate_otp()
        expires_at = timezone.now() + timezone.timedelta(minutes=10)

        return cls.objects.create(
            email=email,
            otp_code=otp_code,
            purpose=purpose,
            expires_at=expires_at
        )

class UserProfile(models.Model):
    """Профиль пользователя"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    first_name = models.CharField(max_length=30, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=30, blank=True, verbose_name="Фамилия")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Аватар")
    date_of_birth = models.DateField(blank=True, null=True, verbose_name="Дата рождения")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"{self.user.username} - {self.first_name} {self.last_name}"

class UserSettings(models.Model):
    """Настройки пользователя"""
    THEME_CHOICES = [
        ('light', 'Светлая тема'),
        ('dark', 'Темная тема'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='light', verbose_name="Тема")
    notifications_enabled = models.BooleanField(default=True, verbose_name="Уведомления включены")
    email_newsletter = models.BooleanField(default=False, verbose_name="Подписка на новости")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Настройки пользователя"
        verbose_name_plural = "Настройки пользователей"

    def __str__(self):
        return f"{self.user.username} - {self.get_theme_display()}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Автоматически создавать профиль и настройки при создании пользователя"""
    if created:
        UserProfile.objects.create(user=instance)
        UserSettings.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Сохранять профиль и настройки при сохранении пользователя"""
    try:
        instance.profile.save()
        instance.settings.save()
    except:
        pass

class Cart(models.Model):
    """Корзина пользователя"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"

    def __str__(self):
        return f"Корзина {self.user.username}"

    @property
    def total_items(self):
        """Общее количество товаров в корзине"""
        return sum(item.quantity for item in self.items.all())

    @property
    def total_price(self):
        """Общая стоимость товаров в корзине"""
        return sum(item.total_price for item in self.items.all())

class CartItem(models.Model):
    """Элемент корзины"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE, null=True, blank=True)
    pigment = models.ForeignKey(Pigment, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Элемент корзины"
        verbose_name_plural = "Элементы корзины"
        unique_together = ['cart', 'perfume', 'pigment']  # Только один из perfume или pigment может быть не null

    def __str__(self):
        product = self.perfume or self.pigment
        return f"{product.name} x {self.quantity}"

    @property
    def product(self):
        """Возвращает продукт (парфюм или пигмент)"""
        return self.perfume or self.pigment

    @property
    def product_type(self):
        """Возвращает тип продукта"""
        return 'perfume' if self.perfume else 'pigment'

    @property
    def unit_price(self):
        """Цена за единицу"""
        return self.product.price

    @property
    def total_price(self):
        """Общая стоимость позиции"""
        return self.unit_price * self.quantity

class Order(models.Model):
    """Заказ"""
    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачен'),
        ('processing', 'В обработке'),
        ('shipped', 'Отправлен'),
        ('delivered', 'Доставлен'),
        ('cancelled', 'Отменен'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('card', 'Банковская карта'),
        ('cash', 'Наличными при получении'),
        ('transfer', 'Банковский перевод'),
        ('yookassa', 'ЮKassa'),
        ('tinkoff', 'Тинькофф'),
    ]
    
    DELIVERY_METHOD_CHOICES = [
        ('cdek', 'CDEK'),
        ('russian_post', 'Почта России'),
        ('pickup', 'Самовывоз'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='card', verbose_name="Способ оплаты")
    payment_id = models.CharField(max_length=100, blank=True, verbose_name="ID платежа в платежной системе")

    # Адрес доставки
    delivery_address = models.TextField(verbose_name="Адрес доставки")
    delivery_city = models.CharField(max_length=100, verbose_name="Город")
    delivery_postal_code = models.CharField(max_length=20, verbose_name="Почтовый индекс")
    delivery_phone = models.CharField(max_length=20, verbose_name="Телефон для доставки")
    
    # Информация о доставке
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHOD_CHOICES, blank=True, verbose_name="Способ доставки")
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name="Трекинг-номер")
    delivery_service_order_id = models.CharField(max_length=100, blank=True, verbose_name="ID заказа в службе доставки")
    estimated_delivery_date = models.DateField(null=True, blank=True, verbose_name="Ожидаемая дата доставки")

    # Суммы
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма без доставки")
    delivery_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Стоимость доставки")
    total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Итоговая сумма")

    # Даты
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата оплаты")
    shipped_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата отправки")
    delivered_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата доставки")

    # Комментарии
    customer_notes = models.TextField(blank=True, verbose_name="Комментарий покупателя")
    admin_notes = models.TextField(blank=True, verbose_name="Комментарий администратора")

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']

    def __str__(self):
        return f"Заказ #{self.id} - {self.user.username}"

    def save(self, *args, **kwargs):
        """Автоматически рассчитывать итоговую сумму"""
        if not self.delivery_cost:
            self.delivery_cost = 0
        self.total = self.subtotal + self.delivery_cost
        super().save(*args, **kwargs)

class OrderItem(models.Model):
    """Позиция заказа"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    perfume = models.ForeignKey(Perfume, on_delete=models.SET_NULL, null=True, blank=True)
    pigment = models.ForeignKey(Pigment, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=200, verbose_name="Название товара")  # Сохраняем на случай удаления товара
    product_sku = models.CharField(max_length=100, blank=True, verbose_name="Артикул товара")
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена за единицу")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Общая стоимость")

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказов"

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    @property
    def product(self):
        """Возвращает продукт (парфюм или пигмент)"""
        return self.perfume or self.pigment

    @property
    def product_type(self):
        """Возвращает тип продукта"""
        return 'perfume' if self.perfume else 'pigment'

    def save(self, *args, **kwargs):
        """Автоматически рассчитывать общую стоимость"""
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)

@receiver(post_save, sender=User)
def create_user_cart(sender, instance, created, **kwargs):
    """Автоматически создавать корзину при создании пользователя"""
    if created:
        Cart.objects.create(user=instance)
