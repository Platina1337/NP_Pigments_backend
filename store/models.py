from django.db import models, transaction
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal, ROUND_DOWN
import random
import string
import secrets

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
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True, verbose_name="Slug")
    sku = models.CharField(max_length=64, unique=True, blank=True, null=True, verbose_name="Артикул")
    description = models.TextField(blank=True, verbose_name="Описание")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='U', verbose_name="Пол")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Цена")
    discount_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Скидка (%)",
        help_text="Процент скидки (0-100)",
    )
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Цена со скидкой",
        help_text="Если указано, используется вместо расчета по проценту",
    )
    discount_start_date = models.DateTimeField(blank=True, null=True, verbose_name="Начало акции")
    discount_end_date = models.DateTimeField(blank=True, null=True, verbose_name="Конец акции")
    volume_ml = models.PositiveIntegerField(verbose_name="Объем (мл)")
    concentration = models.CharField(max_length=50, blank=True, verbose_name="Концентрация")
    top_notes = models.TextField(blank=True, verbose_name="Верхние ноты")
    heart_notes = models.TextField(blank=True, verbose_name="Средние ноты")
    base_notes = models.TextField(blank=True, verbose_name="Базовые ноты")
    image = models.ImageField(upload_to='perfumes/', blank=True, null=True, verbose_name="Изображение")
    in_stock = models.BooleanField(default=True, verbose_name="В наличии")
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    featured = models.BooleanField(default=False, verbose_name="Рекомендуемый")
    discount_source = models.ForeignKey(
        'Promotion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discounted_perfumes',
        verbose_name="Источник акции",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Парфюм"
        verbose_name_plural = "Парфюмы"
        ordering = ['-created_at']

    def get_discounted_price(self):
        """Возвращает цену со скидкой или обычную цену"""
        now = timezone.now()

        # Проверяем, активна ли скидка по датам
        if self.discount_start_date and self.discount_end_date:
            if not (self.discount_start_date <= now <= self.discount_end_date):
                return self.price
        elif self.discount_start_date and self.discount_start_date > now:
            return self.price
        elif self.discount_end_date and self.discount_end_date < now:
            return self.price

        # Если указана фиксированная цена скидки
        if self.discount_price and self.discount_price > 0:
            return self.discount_price

        # Если указан процент скидки
        if self.discount_percentage > 0:
            discount_amount = self.price * (self.discount_percentage / Decimal('100'))
            return self.price - discount_amount

        return self.price

    def is_on_sale(self):
        """Проверяет, есть ли активная скидка"""
        now = timezone.now()

        if self.discount_start_date and self.discount_end_date:
            return self.discount_start_date <= now <= self.discount_end_date
        elif self.discount_start_date:
            return self.discount_start_date <= now
        elif self.discount_end_date:
            return now <= self.discount_end_date

        return self.discount_percentage > 0 or (self.discount_price and self.discount_price > 0)

    def get_discount_percentage_display(self):
        """Возвращает процент скидки для отображения"""
        if self.discount_price and self.discount_price > 0:
            discount_percent = ((self.price - self.discount_price) / self.price) * 100
            return round(discount_percent)
        return self.discount_percentage

    def __str__(self):
        return f"{self.brand.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or f"perfume-{self.pk or ''}"
            slug = base
            counter = 1
            while Perfume.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def min_price(self):
        """Returns minimum price across all volume options"""
        options = self.volume_options.filter(in_stock=True)
        if options.exists():
            return min(opt.get_discounted_price() for opt in options)
        return self.get_discounted_price()

    @property
    def max_price(self):
        """Returns maximum price across all volume options"""
        options = self.volume_options.filter(in_stock=True)
        if options.exists():
            return max(opt.get_discounted_price() for opt in options)
        return self.get_discounted_price()

    @property
    def has_multiple_volumes(self):
        """Check if product has multiple volume options"""
        return self.volume_options.count() > 1

    @property
    def default_volume_option(self):
        """Returns the default volume option or the first one"""
        return self.volume_options.filter(is_default=True).first() or self.volume_options.first()


class VolumeOption(models.Model):
    """Volume variant for perfume with its own price and stock"""
    perfume = models.ForeignKey(
        Perfume,
        on_delete=models.CASCADE,
        related_name='volume_options',
        verbose_name="Парфюм"
    )
    volume_ml = models.PositiveIntegerField(verbose_name="Объем (мл)")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Цена"
    )
    discount_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Скидка (%)",
        help_text="Процент скидки (0-100)"
    )
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Цена со скидкой",
        help_text="Если указано, используется вместо расчета по проценту"
    )
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    in_stock = models.BooleanField(default=True, verbose_name="В наличии")
    is_default = models.BooleanField(default=False, verbose_name="По умолчанию")

    class Meta:
        verbose_name = "Вариант объема"
        verbose_name_plural = "Варианты объема"
        ordering = ['volume_ml']
        unique_together = ['perfume', 'volume_ml']

    def __str__(self):
        return f"{self.perfume.name} - {self.volume_ml} мл"

    def get_discounted_price(self):
        """Returns discounted price or regular price"""
        # Inherit discount from parent perfume if not set locally
        if self.discount_price and self.discount_price > 0:
            return self.discount_price
        if self.discount_percentage > 0:
            discount_amount = self.price * (self.discount_percentage / Decimal('100'))
            return self.price - discount_amount
        # Fall back to parent perfume's discount
        if self.perfume.is_on_sale():
            if self.perfume.discount_percentage > 0:
                discount_amount = self.price * (self.perfume.discount_percentage / Decimal('100'))
                return self.price - discount_amount
        return self.price

    def is_on_sale(self):
        """Check if this volume option is on sale"""
        if self.discount_percentage > 0 or (self.discount_price and self.discount_price > 0):
            return True
        return self.perfume.is_on_sale()

    def save(self, *args, **kwargs):
        # If this is set as default, unset other defaults for the same perfume
        if self.is_default:
            VolumeOption.objects.filter(perfume=self.perfume, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


@receiver(post_save, sender=VolumeOption)
def ensure_base_volume_option(sender, instance, created, **kwargs):
    """
    When the first volume option is added, if it's different from the base volume,
    create a volume option for the base volume to ensure it's not lost.
    """
    if created:
        perfume = instance.perfume
        # Check if this is the first option (or close to it) and base volume is not represented
        if perfume.volume_options.count() == 1 and instance.volume_ml != perfume.volume_ml:
            # Create option for base volume
            VolumeOption.objects.create(
                perfume=perfume,
                volume_ml=perfume.volume_ml,
                price=perfume.price,
                stock_quantity=perfume.stock_quantity,
                in_stock=perfume.in_stock,
                is_default=True # Make base volume default to preserve behavior
            )


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
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True, verbose_name="Slug")
    sku = models.CharField(max_length=64, unique=True, blank=True, null=True, verbose_name="Артикул")
    description = models.TextField(blank=True, verbose_name="Описание")
    color_code = models.CharField(max_length=20, blank=True, verbose_name="Код цвета")
    color_type = models.CharField(max_length=20, choices=COLOR_TYPES, default='powder', verbose_name="Тип цвета")
    application_type = models.CharField(max_length=20, choices=APPLICATION_TYPES, default='cosmetics', verbose_name="Применение")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Цена")
    discount_percentage = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="Скидка (%)",
                                                     help_text="Процент скидки (0-100)")
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Цена со скидкой",
                                        help_text="Если указано, используется вместо расчета по проценту")
    discount_start_date = models.DateTimeField(blank=True, null=True, verbose_name="Начало акции")
    discount_end_date = models.DateTimeField(blank=True, null=True, verbose_name="Конец акции")
    weight_gr = models.PositiveIntegerField(verbose_name="Вес (г)")
    image = models.ImageField(upload_to='pigments/', blank=True, null=True, verbose_name="Изображение")
    in_stock = models.BooleanField(default=True, verbose_name="В наличии")
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    featured = models.BooleanField(default=False, verbose_name="Рекомендуемый")
    discount_source = models.ForeignKey(
        'Promotion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discounted_pigments',
        verbose_name="Источник акции",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Пигмент"
        verbose_name_plural = "Пигменты"
        ordering = ['-created_at']

    def get_discounted_price(self):
        """Возвращает цену со скидкой или обычную цену"""
        now = timezone.now()

        # Проверяем, активна ли скидка по датам
        if self.discount_start_date and self.discount_end_date:
            if not (self.discount_start_date <= now <= self.discount_end_date):
                return self.price
        elif self.discount_start_date and self.discount_start_date > now:
            return self.price
        elif self.discount_end_date and self.discount_end_date < now:
            return self.price

        # Если указана фиксированная цена скидки
        if self.discount_price and self.discount_price > 0:
            return self.discount_price

        # Если указан процент скидки
        if self.discount_percentage > 0:
            discount_amount = self.price * (self.discount_percentage / Decimal('100'))
            return self.price - discount_amount

        return self.price

    def is_on_sale(self):
        """Проверяет, есть ли активная скидка"""
        now = timezone.now()

        if self.discount_start_date and self.discount_end_date:
            return self.discount_start_date <= now <= self.discount_end_date
        elif self.discount_start_date:
            return self.discount_start_date <= now
        elif self.discount_end_date:
            return now <= self.discount_end_date

        return self.discount_percentage > 0 or (self.discount_price and self.discount_price > 0)

    def get_discount_percentage_display(self):
        """Возвращает процент скидки для отображения"""
        if self.discount_price and self.discount_price > 0:
            discount_percent = ((self.price - self.discount_price) / self.price) * 100
            return round(discount_percent)
        return self.discount_percentage

    def __str__(self):
        return f"{self.brand.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or f"pigment-{self.pk or ''}"
            slug = base
            counter = 1
            while Pigment.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def min_price(self):
        """Returns minimum price across all weight options"""
        options = self.weight_options.filter(in_stock=True)
        if options.exists():
            return min(opt.get_discounted_price() for opt in options)
        return self.get_discounted_price()

    @property
    def max_price(self):
        """Returns maximum price across all weight options"""
        options = self.weight_options.filter(in_stock=True)
        if options.exists():
            return max(opt.get_discounted_price() for opt in options)
        return self.get_discounted_price()

    @property
    def has_multiple_weights(self):
        """Check if product has multiple weight options"""
        return self.weight_options.count() > 1

    @property
    def default_weight_option(self):
        """Returns the default weight option or the first one"""
        return self.weight_options.filter(is_default=True).first() or self.weight_options.first()


class WeightOption(models.Model):
    """Weight variant for pigment with its own price and stock"""
    pigment = models.ForeignKey(
        Pigment,
        on_delete=models.CASCADE,
        related_name='weight_options',
        verbose_name="Пигмент"
    )
    weight_gr = models.PositiveIntegerField(verbose_name="Вес (г)")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Цена"
    )
    discount_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Скидка (%)",
        help_text="Процент скидки (0-100)"
    )
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Цена со скидкой",
        help_text="Если указано, используется вместо расчета по проценту"
    )
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    in_stock = models.BooleanField(default=True, verbose_name="В наличии")
    is_default = models.BooleanField(default=False, verbose_name="По умолчанию")

    class Meta:
        verbose_name = "Вариант веса"
        verbose_name_plural = "Варианты веса"
        ordering = ['weight_gr']
        unique_together = ['pigment', 'weight_gr']

    def __str__(self):
        return f"{self.pigment.name} - {self.weight_gr} г"

    def get_discounted_price(self):
        """Returns discounted price or regular price"""
        if self.discount_price and self.discount_price > 0:
            return self.discount_price
        if self.discount_percentage > 0:
            discount_amount = self.price * (self.discount_percentage / Decimal('100'))
            return self.price - discount_amount
        # Fall back to parent pigment's discount
        if self.pigment.is_on_sale():
            if self.pigment.discount_percentage > 0:
                discount_amount = self.price * (self.pigment.discount_percentage / Decimal('100'))
                return self.price - discount_amount
        return self.price

    def is_on_sale(self):
        """Check if this weight option is on sale"""
        if self.discount_percentage > 0 or (self.discount_price and self.discount_price > 0):
            return True
        return self.pigment.is_on_sale()

    def save(self, *args, **kwargs):
        # If this is set as default, unset other defaults for the same pigment
        if self.is_default:
            WeightOption.objects.filter(pigment=self.pigment, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


@receiver(post_save, sender=WeightOption)
def ensure_base_weight_option(sender, instance, created, **kwargs):
    """
    When the first weight option is added, if it's different from the base weight,
    create a weight option for the base weight to ensure it's not lost.
    """
    if created:
        pigment = instance.pigment
        # Check if this is the first option (or close to it) and base weight is not represented
        if pigment.weight_options.count() == 1 and instance.weight_gr != pigment.weight_gr:
            # Create option for base weight
            WeightOption.objects.create(
                pigment=pigment,
                weight_gr=pigment.weight_gr,
                price=pigment.price,
                stock_quantity=pigment.stock_quantity,
                in_stock=pigment.in_stock,
                is_default=True # Make base weight default
            )


class TrendingProduct(models.Model):
    """Подборка 'В тренде сейчас'."""

    PRODUCT_TYPES = [
        ('perfume', 'Парфюм'),
        ('pigment', 'Пигмент'),
    ]

    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPES, verbose_name="Тип товара")
    perfume = models.ForeignKey(Perfume, null=True, blank=True, on_delete=models.CASCADE, verbose_name="Парфюм")
    pigment = models.ForeignKey(Pigment, null=True, blank=True, on_delete=models.CASCADE, verbose_name="Пигмент")
    position = models.PositiveIntegerField(default=0, verbose_name="Позиция")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Трендовый товар"
        verbose_name_plural = "Трендовые товары"
        ordering = ['position', '-created_at']

    def product(self):
        return self.perfume if self.product_type == 'perfume' else self.pigment

    def __str__(self):
        prod = self.product()
        return f"{self.get_product_type_display()}: {prod}" if prod else f"Тренд {self.pk}"

class Promotion(models.Model):
    """Акция/промо для витрин и применения скидок."""

    PROMO_TYPES = [
        ('brand', 'Бренд'),
        ('category', 'Категория'),
        ('manual', 'Ручной выбор'),
        ('all', 'Все товары'),
    ]

    PROMO_SLOTS = [
        ('homepage_deals_1', 'Главная — блок акций 1'),
        ('homepage_deals_2', 'Главная — блок акций 2'),
        ('homepage_deals_3', 'Главная — блок акций 3'),
    ]

    title = models.CharField(max_length=255, verbose_name="Название акции", blank=True)
    promo_type = models.CharField(max_length=20, choices=PROMO_TYPES, default='manual', verbose_name="Тип акции")
    slot = models.CharField(max_length=50, choices=PROMO_SLOTS, default='homepage_deals_1', verbose_name="Слот показа")
    priority = models.IntegerField(default=0, verbose_name="Приоритет (меньше — выше)")
    active = models.BooleanField(default=False, verbose_name="Активна")
    start_at = models.DateTimeField(null=True, blank=True, verbose_name="Начало акции")
    end_at = models.DateTimeField(null=True, blank=True, verbose_name="Конец акции")

    discount_percentage = models.PositiveIntegerField(default=0, verbose_name="Скидка, %", validators=[MinValueValidator(0)])
    discount_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Фиксированная цена со скидкой"
    )

    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Бренд")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Категория")

    perfumes = models.ManyToManyField(Perfume, blank=True, related_name='promotions', verbose_name="Парфюмы")
    pigments = models.ManyToManyField(Pigment, blank=True, related_name='promotions', verbose_name="Пигменты")

    apply_prices = models.BooleanField(default=True, verbose_name="Применять скидку к товарам")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"
        ordering = ['priority', '-created_at']

    def __str__(self):
        return self.title or f"Акция {self.pk}"

    def _product_queryset(self):
        # Собираем товары по типу
        perfumes_qs = Perfume.objects.all()
        pigments_qs = Pigment.objects.all()

        if self.promo_type == 'brand' and self.brand:
            perfumes_qs = perfumes_qs.filter(brand=self.brand)
            pigments_qs = pigments_qs.filter(brand=self.brand)
        if self.promo_type == 'category' and self.category:
            perfumes_qs = perfumes_qs.filter(category=self.category)
            pigments_qs = pigments_qs.filter(category=self.category)
        if self.promo_type == 'manual':
            perfumes_qs = self.perfumes.all()
            pigments_qs = self.pigments.all()
        # promo_type == 'all' оставляет все
        return perfumes_qs, pigments_qs

    def apply_discounts(self):
        """Применяет скидки к товарам, перетирая существующие."""
        perfumes_qs, pigments_qs = self._product_queryset()
        now = timezone.now()
        start = self.start_at or now
        end = self.end_at

        with transaction.atomic():
            for p in perfumes_qs:
                p.discount_percentage = self.discount_percentage
                p.discount_price = self.discount_price
                p.discount_start_date = start
                p.discount_end_date = end
                p.discount_source = self
                p.save(update_fields=[
                    'discount_percentage', 'discount_price',
                    'discount_start_date', 'discount_end_date', 'discount_source', 'updated_at'
                ])
            for g in pigments_qs:
                g.discount_percentage = self.discount_percentage
                g.discount_price = self.discount_price
                g.discount_start_date = start
                g.discount_end_date = end
                g.discount_source = self
                g.save(update_fields=[
                    'discount_percentage', 'discount_price',
                    'discount_start_date', 'discount_end_date', 'discount_source', 'updated_at'
                ])
        self.active = True
        self.save(update_fields=['active', 'updated_at'])

    def clear_discounts(self):
        """Сбрасывает скидки только у товаров, где discount_source == эта акция."""
        with transaction.atomic():
            perfumes_qs = Perfume.objects.filter(discount_source=self)
            pigments_qs = Pigment.objects.filter(discount_source=self)
            for p in perfumes_qs:
                p.discount_percentage = 0
                p.discount_price = None
                p.discount_start_date = None
                p.discount_end_date = None
                p.discount_source = None
                p.save(update_fields=[
                    'discount_percentage', 'discount_price',
                    'discount_start_date', 'discount_end_date', 'discount_source', 'updated_at'
                ])
            for g in pigments_qs:
                g.discount_percentage = 0
                g.discount_price = None
                g.discount_start_date = None
                g.discount_end_date = None
                g.discount_source = None
                g.save(update_fields=[
                    'discount_percentage', 'discount_price',
                    'discount_start_date', 'discount_end_date', 'discount_source', 'updated_at'
                ])
        self.active = False
        self.save(update_fields=['active', 'updated_at'])


class ProductImage(models.Model):
    """Модель для хранения нескольких изображений продукта"""
    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE, related_name='images', null=True, blank=True)
    pigment = models.ForeignKey(Pigment, on_delete=models.CASCADE, related_name='images', null=True, blank=True)
    image = models.ImageField(upload_to='products/', verbose_name="Изображение")
    alt_text = models.CharField(max_length=255, blank=True, verbose_name="Альтернативный текст")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Изображение продукта"
        verbose_name_plural = "Изображения продуктов"
        ordering = ['created_at']

    def __str__(self):
        if self.perfume:
            return f"Image for {self.perfume.name}"
        if self.pigment:
            return f"Image for {self.pigment.name}"
        return "Unassigned Image"


class EmailOTP(models.Model):
    """Модель для одноразовых кодов подтверждения по email"""
    email = models.EmailField(verbose_name="Email")
    otp_code = models.CharField(max_length=6, verbose_name="OTP код")
    magic_token = models.CharField(max_length=64, unique=True, blank=True, null=True, verbose_name="Магический токен")
    register_data = models.TextField(blank=True, null=True, verbose_name="Данные регистрации (JSON)")
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

    @staticmethod
    def generate_magic_token():
        """Генерирует уникальный магический токен для мгновенной авторизации"""
        return secrets.token_urlsafe(48)

    @classmethod
    def create_otp(cls, email, purpose='login', register_data=None):
        """Создает новый OTP код с магическим токеном"""
        # Удаляем старые неиспользованные коды для этого email
        cls.objects.filter(
            email=email,
            purpose=purpose,
            is_used=False
        ).delete()

        # Создаем новый код с магическим токеном
        otp_code = cls.generate_otp()
        magic_token = cls.generate_magic_token()
        expires_at = timezone.now() + timezone.timedelta(minutes=10)
        
        # Сериализуем данные регистрации
        register_data_json = None
        if register_data:
            import json
            register_data_json = json.dumps(register_data)

        return cls.objects.create(
            email=email,
            otp_code=otp_code,
            magic_token=magic_token,
            purpose=purpose,
            expires_at=expires_at,
            register_data=register_data_json
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


class LoyaltyAccount(models.Model):
    """Счет программы лояльности пользователя"""
    TIER_CHOICES = [
        ('bronze', 'Бронза'),
        ('silver', 'Серебро'),
        ('gold', 'Золото'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='loyalty_account')
    balance = models.PositiveIntegerField(default=0, verbose_name="Баллы на счете")
    lifetime_earned = models.PositiveIntegerField(default=0, verbose_name="Всего начислено")
    lifetime_redeemed = models.PositiveIntegerField(default=0, verbose_name="Всего потрачено")
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='bronze', verbose_name="Уровень")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Счет лояльности"
        verbose_name_plural = "Счета лояльности"

    def __str__(self):
        return f"LoyaltyAccount({self.user.username}): {self.balance} баллов"


class LoyaltyTransaction(models.Model):
    """Транзакции по баллам лояльности"""
    TYPE_CHOICES = [
        ('earn', 'Начисление'),
        ('redeem', 'Списание'),
        ('refund', 'Возврат списания'),
        ('adjust', 'Корректировка'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loyalty_transactions')
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='loyalty_transactions')
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    points = models.IntegerField(verbose_name="Изменение баллов (может быть отрицательным)")
    description = models.TextField(blank=True, verbose_name="Комментарий")
    balance_after = models.IntegerField(default=0, verbose_name="Баланс после операции")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Транзакция лояльности"
        verbose_name_plural = "Транзакции лояльности"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.transaction_type} {self.points}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Автоматически создавать профиль и настройки при создании пользователя"""
    # Не создавать автоматически для неактивных пользователей (временные для OTP)
    if created and instance.is_active:
        # Создаем пустой профиль (данные профиля заполняются отдельно при регистрации)
        UserProfile.objects.get_or_create(user=instance)
        UserSettings.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Сохранять профиль и настройки при сохранении пользователя"""
    try:
        instance.profile.save()
        instance.settings.save()
    except:
        pass

class Wishlist(models.Model):
    """Список избранных товаров пользователя"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wishlist')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"

    def __str__(self):
        return f"Избранное {self.user.username}"

    @property
    def total_items(self):
        return self.items.count()

class WishlistItem(models.Model):
    """Конкретный товар в списке избранного"""
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE, null=True, blank=True)
    pigment = models.ForeignKey(Pigment, on_delete=models.CASCADE, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Элемент избранного"
        verbose_name_plural = "Элементы избранного"
        unique_together = ['wishlist', 'perfume', 'pigment']

    def __str__(self):
        product = self.perfume or self.pigment
        return f"{product.name} в избранном"

    @property
    def product(self):
        return self.perfume or self.pigment

    @property
    def product_type(self):
        return 'perfume' if self.perfume else 'pigment'

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
    volume_option = models.ForeignKey(
        'VolumeOption',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Выбранный объем"
    )
    weight_option = models.ForeignKey(
        'WeightOption',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Выбранный вес"
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Элемент корзины"
        verbose_name_plural = "Элементы корзины"
        unique_together = ['cart', 'perfume', 'pigment', 'volume_option', 'weight_option']

    def __str__(self):
        product = self.perfume or self.pigment
        variant = ""
        if self.volume_option:
            variant = f" ({self.volume_option.volume_ml} мл)"
        elif self.weight_option:
            variant = f" ({self.weight_option.weight_gr} г)"
        return f"{product.name}{variant} x {self.quantity}"

    @property
    def product(self):
        """Возвращает продукт (парфюм или пигмент)"""
        return self.perfume or self.pigment

    @property
    def product_type(self):
        """Возвращает тип продукта"""
        return 'perfume' if self.perfume else 'pigment'

    @property
    def selected_volume_ml(self):
        """Returns selected volume in ml"""
        if self.volume_option:
            return self.volume_option.volume_ml
        if self.perfume:
            return self.perfume.volume_ml
        return None

    @property
    def selected_weight_gr(self):
        """Returns selected weight in grams"""
        if self.weight_option:
            return self.weight_option.weight_gr
        if self.pigment:
            return self.pigment.weight_gr
        return None

    @property
    def unit_price(self):
        """Цена за единицу"""
        # Use selected variant price if available
        if self.volume_option:
            return self.volume_option.get_discounted_price()
        if self.weight_option:
            return self.weight_option.get_discounted_price()
        # Fall back to product price
        product = self.product
        if not product:
            return Decimal('0')
        if hasattr(product, 'get_discounted_price'):
            return product.get_discounted_price()
        return product.price

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
    loyalty_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Скидка баллами")
    loyalty_points_used = models.PositiveIntegerField(default=0, verbose_name="Потраченные баллы")
    loyalty_points_earned = models.PositiveIntegerField(default=0, verbose_name="Начисленные баллы")
    loyalty_awarded = models.BooleanField(default=False, verbose_name="Баллы начислены")
    loyalty_refunded = models.BooleanField(default=False, verbose_name="Баллы возвращены")
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
        """Автоматический расчет итоговой суммы и начисление/возврат баллов"""
        # Сохраняем предыдущие значения для отслеживания смены статуса
        previous_status = None
        previous_awarded = self.loyalty_awarded
        previous_refunded = self.loyalty_refunded

        if self.pk:
            try:
                previous = Order.objects.only('status', 'loyalty_awarded', 'loyalty_refunded').get(pk=self.pk)
                previous_status = previous.status
                previous_awarded = previous.loyalty_awarded
                previous_refunded = previous.loyalty_refunded
            except Order.DoesNotExist:
                pass

        # Нормализуем суммы
        if not self.delivery_cost:
            self.delivery_cost = Decimal('0')
        if not self.loyalty_discount:
            self.loyalty_discount = Decimal('0')

        # Пересчитываем total с учетом скидки баллами (не даем уйти в минус)
        self.total = (self.subtotal - self.loyalty_discount + self.delivery_cost)
        if self.total < 0:
            self.total = Decimal('0')

        super().save(*args, **kwargs)

        # Начисление или возврат баллов выполняем после сохранения заказа
        should_award = (
            self.status in ['paid', 'delivered']
            and not previous_awarded
            and not self.loyalty_awarded
        )
        should_refund = (
            self.status == 'cancelled'
            and self.loyalty_points_used > 0
            and not previous_refunded
            and not self.loyalty_refunded
        )

        if (should_award or should_refund) and self.user_id:
            with transaction.atomic():
                account, _ = LoyaltyAccount.objects.select_for_update().get_or_create(user=self.user)

                if should_award:
                    base_amount = max(self.subtotal - self.loyalty_discount, Decimal('0'))
                    earn_rate = Decimal('0.05')  # 5% кэшбэка в баллах
                    earned_points = int((base_amount * earn_rate).quantize(Decimal('1'), rounding=ROUND_DOWN))

                    if earned_points > 0:
                        account.balance += earned_points
                        account.lifetime_earned += earned_points
                        account.save(update_fields=['balance', 'lifetime_earned', 'updated_at'])

                        LoyaltyTransaction.objects.create(
                            user=self.user,
                            order=self,
                            transaction_type='earn',
                            points=earned_points,
                            description=f'Начисление за заказ #{self.id}',
                            balance_after=account.balance,
                        )

                    Order.objects.filter(pk=self.pk).update(
                        loyalty_points_earned=earned_points,
                        loyalty_awarded=True,
                    )

                if should_refund:
                    refund_points = self.loyalty_points_used
                    account.balance += refund_points
                    account.lifetime_redeemed = max(account.lifetime_redeemed - refund_points, 0)
                    account.save(update_fields=['balance', 'lifetime_redeemed', 'updated_at'])

                    LoyaltyTransaction.objects.create(
                        user=self.user,
                        order=self,
                        transaction_type='refund',
                        points=refund_points,
                        description=f'Возврат баллов за отмененный заказ #{self.id}',
                        balance_after=account.balance,
                    )

                    Order.objects.filter(pk=self.pk).update(
                        loyalty_refunded=True,
                    )

class OrderItem(models.Model):
    """Позиция заказа"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    perfume = models.ForeignKey(Perfume, on_delete=models.SET_NULL, null=True, blank=True)
    pigment = models.ForeignKey(Pigment, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=200, verbose_name="Название товара")  # Сохраняем на случай удаления товара
    product_sku = models.CharField(max_length=100, blank=True, verbose_name="Артикул товара")
    selected_volume_ml = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Выбранный объем (мл)"
    )
    selected_weight_gr = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Выбранный вес (г)"
    )
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена за единицу")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Общая стоимость")

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказов"

    def __str__(self):
        variant = ""
        if self.selected_volume_ml:
            variant = f" ({self.selected_volume_ml} мл)"
        elif self.selected_weight_gr:
            variant = f" ({self.selected_weight_gr} г)"
        return f"{self.product_name}{variant} x {self.quantity}"

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

@receiver(post_save, sender=User)
def create_user_wishlist(sender, instance, created, **kwargs):
    """Автоматически создавать список избранного при создании пользователя"""
    if created:
        Wishlist.objects.create(user=instance)


@receiver(post_save, sender=User)
def create_loyalty_account(sender, instance, created, **kwargs):
    """Создаем счет лояльности при регистрации пользователя"""
    if created:
        LoyaltyAccount.objects.get_or_create(user=instance)
