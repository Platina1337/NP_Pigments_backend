from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import (
    Brand, Category, Perfume, Pigment,
    UserProfile, UserSettings, Cart, CartItem,
    Order, OrderItem, EmailOTP, ProductImage,
    VolumeOption, WeightOption
)


# Inline админки для вариантов объема/веса
class VolumeOptionInline(admin.TabularInline):
    model = VolumeOption
    extra = 1
    fields = ('volume_ml', 'price', 'discount_percentage', 'discount_price', 'stock_quantity', 'in_stock', 'is_default')
    ordering = ['volume_ml']


class WeightOptionInline(admin.TabularInline):
    model = WeightOption
    extra = 1
    fields = ('weight_gr', 'price', 'discount_percentage', 'discount_price', 'stock_quantity', 'in_stock', 'is_default')
    ordering = ['weight_gr']


# Inline админки для изображений
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1  # Количество пустых форм для загрузки
    fields = ('image', 'alt_text', 'image_preview')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="150" style="object-fit: contain;" />', obj.image.url)
        return "Нет изображения"
    image_preview.short_description = "Превью"

class PerfumeImageInline(ProductImageInline):
    fk_name = "perfume"
    
class PigmentImageInline(ProductImageInline):
    fk_name = "pigment"

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Профиль'
    fk_name = 'user'
    fields = ('first_name', 'last_name', 'phone', 'avatar', 'date_of_birth')


class UserSettingsInline(admin.StackedInline):
    model = UserSettings
    can_delete = False
    verbose_name_plural = 'Настройки'
    fk_name = 'user'
    fields = ('theme', 'notifications_enabled', 'email_newsletter')


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('product_name', 'unit_price', 'total_price')
    fields = ('perfume', 'pigment', 'quantity', 'unit_price', 'total_price')
    
    def product_name(self, obj):
        if obj.product:
            return obj.product.name
        return "-"
    product_name.short_description = "Товар"
    
    def unit_price(self, obj):
        if obj.product:
            return f"{obj.product.price} ₽"
        return "-"
    unit_price.short_description = "Цена"
    
    def total_price(self, obj):
        if obj.product:
            return f"{obj.product.price * obj.quantity} ₽"
        return "-"
    total_price.short_description = "Сумма"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'unit_price', 'quantity', 'total_price')
    fields = ('product_name', 'unit_price', 'quantity', 'total_price')
    can_delete = False


# Расширенный UserAdmin
class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, UserSettingsInline)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')


# Регистрация Brand
@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'logo_preview', 'created_at')
    list_filter = ('country', 'created_at')
    search_fields = ('name', 'country', 'description')
    readonly_fields = ('created_at', 'logo_preview')
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'country', 'description')
        }),
        ('Медиа', {
            'fields': ('logo', 'logo_preview')
        }),
        ('Даты', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" width="100" height="100" style="object-fit: contain;" />', obj.logo.url)
        return "Нет изображения"
    logo_preview.short_description = "Превью логотипа"


# Регистрация Category
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_type', 'icon', 'created_at')
    list_filter = ('category_type', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'category_type', 'icon', 'description')
        }),
        ('Даты', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


# Регистрация Perfume
@admin.register(Perfume)
class PerfumeAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'price', 'volume_ml', 'gender', 'in_stock', 'stock_quantity', 'featured', 'image_preview')
    list_filter = ('brand', 'category', 'gender', 'in_stock', 'featured', 'created_at')
    search_fields = ('name', 'brand__name', 'category__name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'image_preview')
    list_editable = ('in_stock', 'featured')
    actions = ['mark_in_stock', 'mark_out_of_stock', 'mark_featured', 'unmark_featured']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'brand', 'category', 'gender', 'description')
        }),
        ('Цена и наличие', {
            'fields': ('price', 'volume_ml', 'concentration', 'in_stock', 'stock_quantity', 'featured')
        }),
        ('Ноты аромата', {
            'fields': ('top_notes', 'heart_notes', 'base_notes'),
            'classes': ('collapse',)
        }),
        ('Медиа', {
            'fields': ('image', 'image_preview')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [VolumeOptionInline, PerfumeImageInline]
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="100" style="object-fit: contain;" />', obj.image.url)
        return "Нет изображения"
    image_preview.short_description = "Превью"
    
    @admin.action(description='Отметить как "В наличии"')
    def mark_in_stock(self, request, queryset):
        updated = queryset.update(in_stock=True)
        self.message_user(request, f'{updated} товар(ов) отмечены как "В наличии"')
    
    @admin.action(description='Отметить как "Нет в наличии"')
    def mark_out_of_stock(self, request, queryset):
        updated = queryset.update(in_stock=False)
        self.message_user(request, f'{updated} товар(ов) отмечены как "Нет в наличии"')
    
    @admin.action(description='Отметить как рекомендуемые')
    def mark_featured(self, request, queryset):
        updated = queryset.update(featured=True)
        self.message_user(request, f'{updated} товар(ов) отмечены как рекомендуемые')
    
    @admin.action(description='Убрать из рекомендуемых')
    def unmark_featured(self, request, queryset):
        updated = queryset.update(featured=False)
        self.message_user(request, f'{updated} товар(ов) убраны из рекомендуемых')


# Регистрация Pigment
@admin.register(Pigment)
class PigmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'color_code', 'color_type', 'application_type', 'price', 'weight_gr', 'in_stock', 'stock_quantity', 'featured', 'image_preview')
    list_filter = ('brand', 'category', 'color_type', 'application_type', 'in_stock', 'featured', 'created_at')
    search_fields = ('name', 'brand__name', 'category__name', 'description', 'color_code')
    readonly_fields = ('created_at', 'updated_at', 'image_preview')
    list_editable = ('in_stock', 'featured')
    actions = ['mark_in_stock', 'mark_out_of_stock', 'mark_featured', 'unmark_featured']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'brand', 'category', 'description')
        }),
        ('Характеристики', {
            'fields': ('color_code', 'color_type', 'application_type')
        }),
        ('Цена и наличие', {
            'fields': ('price', 'weight_gr', 'in_stock', 'stock_quantity', 'featured')
        }),
        ('Медиа', {
            'fields': ('image', 'image_preview')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [WeightOptionInline, PigmentImageInline]
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="100" style="object-fit: contain;" />', obj.image.url)
        return "Нет изображения"
    image_preview.short_description = "Превью"
    
    @admin.action(description='Отметить как "В наличии"')
    def mark_in_stock(self, request, queryset):
        updated = queryset.update(in_stock=True)
        self.message_user(request, f'{updated} товар(ов) отмечены как "В наличии"')
    
    @admin.action(description='Отметить как "Нет в наличии"')
    def mark_out_of_stock(self, request, queryset):
        updated = queryset.update(in_stock=False)
        self.message_user(request, f'{updated} товар(ов) отмечены как "Нет в наличии"')
    
    @admin.action(description='Отметить как рекомендуемые')
    def mark_featured(self, request, queryset):
        updated = queryset.update(featured=True)
        self.message_user(request, f'{updated} товар(ов) отмечены как рекомендуемые')
    
    @admin.action(description='Убрать из рекомендуемых')
    def unmark_featured(self, request, queryset):
        updated = queryset.update(featured=False)
        self.message_user(request, f'{updated} товар(ов) убраны из рекомендуемых')


# Регистрация Cart
@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_items_display', 'total_price_display', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'total_items_display', 'total_price_display')
    inlines = [CartItemInline]
    
    def total_items_display(self, obj):
        return obj.total_items
    total_items_display.short_description = "Всего товаров"
    
    def total_price_display(self, obj):
        return f"{obj.total_price} ₽"
    total_price_display.short_description = "Общая сумма"


# Регистрация Order
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'payment_method', 'total', 'created_at', 'paid_at')
    list_filter = ('status', 'payment_method', 'created_at', 'paid_at')
    search_fields = ('user__username', 'user__email', 'delivery_phone', 'delivery_city')
    readonly_fields = ('created_at', 'updated_at', 'paid_at', 'shipped_at', 'delivered_at', 'subtotal', 'total')
    list_editable = ('status',)
    inlines = [OrderItemInline]
    actions = ['mark_as_paid', 'mark_as_processing', 'mark_as_shipped', 'mark_as_delivered', 'mark_as_cancelled']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Информация о заказе', {
            'fields': ('user', 'status', 'payment_method', 'payment_id')
        }),
        ('Адрес доставки', {
            'fields': ('delivery_address', 'delivery_city', 'delivery_postal_code', 'delivery_phone')
        }),
        ('Информация о доставке', {
            'fields': ('delivery_method', 'tracking_number', 'delivery_service_order_id', 'estimated_delivery_date')
        }),
        ('Суммы', {
            'fields': ('subtotal', 'delivery_cost', 'total')
        }),
        ('Комментарии', {
            'fields': ('customer_notes', 'admin_notes'),
            'classes': ('collapse',)
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at', 'paid_at', 'shipped_at', 'delivered_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.action(description='Пометить как "Оплачен"')
    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='paid', paid_at=timezone.now())
        self.message_user(request, f'{updated} заказ(ов) помечены как оплаченные')
    
    @admin.action(description='Пометить как "В обработке"')
    def mark_as_processing(self, request, queryset):
        updated = queryset.update(status='processing')
        self.message_user(request, f'{updated} заказ(ов) помечены как "В обработке"')
    
    @admin.action(description='Пометить как "Отправлен"')
    def mark_as_shipped(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='shipped', shipped_at=timezone.now())
        self.message_user(request, f'{updated} заказ(ов) помечены как отправленные')
    
    @admin.action(description='Пометить как "Доставлен"')
    def mark_as_delivered(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='delivered', delivered_at=timezone.now())
        self.message_user(request, f'{updated} заказ(ов) помечены как доставленные')
    
    @admin.action(description='Отменить заказы')
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} заказ(ов) отменены')


# Регистрация EmailOTP
@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp_code', 'purpose', 'is_used', 'is_expired_status', 'created_at', 'expires_at')
    list_filter = ('purpose', 'is_used', 'created_at')
    search_fields = ('email', 'otp_code')
    readonly_fields = ('created_at', 'is_expired_status')
    
    def is_expired_status(self, obj):
        return obj.is_expired
    is_expired_status.short_description = "Истек"
    is_expired_status.boolean = True


# Перерегистрация User с расширенными инлайнами
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
