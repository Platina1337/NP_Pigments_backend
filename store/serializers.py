from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import (
    Brand,
    Category,
    Perfume,
    Pigment,
    UserProfile,
    UserSettings,
    Cart,
    CartItem,
    Order,
    OrderItem,
    EmailOTP,
    ProductImage,
    Wishlist,
    WishlistItem,
)

def serialize_product_payload(product):
    """Возвращает базовое описание продукта для фронтенда"""
    if not product:
        return None

    base = {
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'price': str(product.price),
        'image': product.image.url if getattr(product, 'image', None) else None,
        'in_stock': product.in_stock,
        'stock_quantity': product.stock_quantity,
        'created_at': product.created_at.isoformat() if product.created_at else None,
        'updated_at': product.updated_at.isoformat() if product.updated_at else None,
        'brand': {
            'id': product.brand.id,
            'name': product.brand.name,
            'description': product.brand.description,
            'country': product.brand.country,
            'created_at': product.brand.created_at.isoformat() if product.brand.created_at else None,
        } if getattr(product, 'brand', None) else None,
        'category': {
            'id': product.category.id,
            'name': product.category.name,
            'description': product.category.description,
            'category_type': getattr(product.category, 'category_type', None),
            'created_at': product.category.created_at.isoformat() if product.category.created_at else None,
        } if getattr(product, 'category', None) else None,
    }

    if isinstance(product, Perfume):
        base.update({
            'product_type': 'perfume',
            'gender': product.gender,
            'volume_ml': product.volume_ml,
            'concentration': product.concentration,
            'top_notes': product.top_notes,
            'heart_notes': product.heart_notes,
            'base_notes': product.base_notes,
        })
    else:
        base.update({
            'product_type': 'pigment',
            'gender': 'U',
            'volume_ml': product.weight_gr,
            'weight_gr': product.weight_gr,
            'color_type': product.color_type,
            'application_type': product.application_type,
            'concentration': '',
            'top_notes': '',
            'heart_notes': '',
            'base_notes': '',
        })

    return base

class ProductImageSerializer(serializers.ModelSerializer):
    """Сериализатор для изображений продукта"""
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text']

class BrandSerializer(serializers.ModelSerializer):
    """Сериализатор для бренда"""
    class Meta:
        model = Brand
        fields = ['id', 'name', 'description', 'country', 'logo', 'created_at']

class CategorySerializer(serializers.ModelSerializer):
    """Сериализатор для категории"""
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'category_type', 'icon', 'created_at']

class PerfumeSerializer(serializers.ModelSerializer):
    """Сериализатор для парфюма"""
    brand = BrandSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    brand_id = serializers.IntegerField(write_only=True)
    category_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Perfume
        fields = [
            'id', 'name', 'brand', 'category', 'brand_id', 'category_id',
            'description', 'gender', 'price', 'volume_ml', 'concentration',
            'top_notes', 'heart_notes', 'base_notes', 'image', 'images', 'in_stock',
            'stock_quantity', 'featured', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class PerfumeListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка парфюмов (упрощенный)"""
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Perfume
        fields = [
            'id', 'name', 'brand_name', 'category_name', 'price',
            'volume_ml', 'gender', 'in_stock', 'image', 'featured'
        ]

class PigmentSerializer(serializers.ModelSerializer):
    """Сериализатор для пигмента"""
    brand = BrandSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    brand_id = serializers.IntegerField(write_only=True)
    category_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Pigment
        fields = [
            'id', 'name', 'brand', 'category', 'brand_id', 'category_id',
            'description', 'color_code', 'color_type', 'application_type',
            'price', 'weight_gr', 'image', 'images', 'in_stock', 'stock_quantity',
            'featured', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class PigmentListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка пигментов (упрощенный)"""
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Pigment
        fields = [
            'id', 'name', 'brand_name', 'category_name', 'price',
            'weight_gr', 'color_type', 'application_type', 'in_stock',
            'image', 'featured'
        ]

# Пользовательские сериализаторы

class UserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор для профиля пользователя"""
    phone = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = UserProfile
        fields = ['first_name', 'last_name', 'phone', 'avatar', 'date_of_birth', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class UserSettingsSerializer(serializers.ModelSerializer):
    """Сериализатор для настроек пользователя"""
    class Meta:
        model = UserSettings
        fields = ['theme', 'notifications_enabled', 'email_newsletter', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class EmailOTPSerializer(serializers.ModelSerializer):
    """Сериализатор для Email OTP"""
    class Meta:
        model = EmailOTP
        fields = ['email', 'purpose']
        read_only_fields = ['otp_code', 'expires_at', 'is_used']

class EmailOTPVerifySerializer(serializers.Serializer):
    """Сериализатор для верификации OTP"""
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    purpose = serializers.ChoiceField(choices=[('login', 'Вход'), ('register', 'Регистрация')])

class UserRegistrationSerializer(serializers.ModelSerializer):
    """Сериализатор для регистрации пользователя"""
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    profile = UserProfileSerializer(required=False)
    settings = UserSettingsSerializer(required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2', 'first_name', 'last_name', 'profile', 'settings']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Пароли не совпадают"})

        # Проверяем уникальность email и username
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({"email": "Пользователь с таким email уже существует"})

        if User.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError({"username": "Пользователь с таким именем уже существует"})

        return attrs

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        settings_data = validated_data.pop('settings', {})
        password2 = validated_data.pop('password2')

        user = User.objects.create_user(**validated_data)
        UserProfile.objects.update_or_create(user=user, defaults=profile_data)
        UserSettings.objects.update_or_create(user=user, defaults=settings_data)

        return user

class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для пользователя"""
    profile = UserProfileSerializer()
    settings = UserSettingsSerializer()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'date_joined', 'profile', 'settings']
        read_only_fields = ['id', 'username', 'email', 'is_active', 'date_joined']

    def update(self, instance, validated_data):
        # Извлекаем данные профиля и настроек
        profile_data = validated_data.pop('profile', {})
        settings_data = validated_data.pop('settings', {})

        # Обновляем основные поля пользователя
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Обновляем профиль пользователя
        if profile_data:
            profile_obj, created = UserProfile.objects.update_or_create(
                user=instance,
                defaults=profile_data
            )
            # Обновляем профиль в памяти instance
            instance.profile = profile_obj

        # Обновляем настройки пользователя
        if settings_data:
            settings_obj, created = UserSettings.objects.update_or_create(
                user=instance,
                defaults=settings_data
            )
            # Обновляем настройки в памяти instance
            instance.settings = settings_obj

        return instance

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Кастомный сериализатор для получения JWT токенов"""
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Добавляем дополнительную информацию в токен
        token['username'] = user.username
        token['email'] = user.email
        token['theme'] = user.settings.theme if hasattr(user, 'settings') else 'light'

        return token

    def validate(self, attrs):
        username_value = attrs.get(self.username_field)
        if username_value:
            normalized = username_value.strip()
            if '@' in normalized:
                try:
                    user = User.objects.get(email__iexact=normalized)
                    attrs[self.username_field] = user.username
                except User.DoesNotExist:
                    attrs[self.username_field] = normalized
            else:
                try:
                    user = User.objects.get(username__iexact=normalized)
                    attrs[self.username_field] = user.username
                except User.DoesNotExist:
                    attrs[self.username_field] = normalized

        data = super().validate(attrs)

        # Добавляем информацию о пользователе в ответ
        user = self.user
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }

        # Добавляем настройки пользователя
        try:
            settings = user.settings
            data['settings'] = {
                'theme': settings.theme,
                'notifications_enabled': settings.notifications_enabled,
                'email_newsletter': settings.email_newsletter,
            }
        except:
            data['settings'] = {
                'theme': 'light',
                'notifications_enabled': True,
                'email_newsletter': False,
            }

        return data

# Сериализаторы для магазина

class CartItemSerializer(serializers.ModelSerializer):
    """Сериализатор для элемента корзины"""
    product_name = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()
    product_type = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    product_data = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            'id',
            'perfume',
            'pigment',
            'quantity',
            'product_name',
            'product_image',
            'product_type',
            'unit_price',
            'total_price',
            'added_at',
            'product_data',
        ]
        read_only_fields = ['id', 'added_at']

    def get_product_name(self, obj):
        return obj.product.name if obj.product else "Товар удален"

    def get_product_image(self, obj):
        return obj.product.image.url if obj.product and obj.product.image else None

    def get_product_type(self, obj):
        return obj.product_type

    def get_unit_price(self, obj):
        return obj.unit_price

    def get_total_price(self, obj):
        return obj.total_price

    def get_product_data(self, obj):
        return serialize_product_payload(obj.product)

class CartSerializer(serializers.ModelSerializer):
    """Сериализатор для корзины"""
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_items', 'total_price', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_total_items(self, obj):
        return obj.total_items

    def get_total_price(self, obj):
        return obj.total_price

class WishlistItemSerializer(serializers.ModelSerializer):
    """Сериализатор для элемента избранного"""
    product_type = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()
    product_price = serializers.SerializerMethodField()
    product_data = serializers.SerializerMethodField()

    class Meta:
        model = WishlistItem
        fields = [
            'id',
            'perfume',
            'pigment',
            'product_type',
            'product_name',
            'product_image',
            'product_price',
            'product_data',
            'added_at',
        ]
        read_only_fields = ['id', 'added_at']

    def get_product_type(self, obj):
        return obj.product_type

    def get_product_name(self, obj):
        product = obj.product
        return product.name if product else None

    def get_product_image(self, obj):
        product = obj.product
        if product and getattr(product, 'image', None):
            return product.image.url
        return None

    def get_product_price(self, obj):
        product = obj.product
        return str(product.price) if product else None

    def get_product_data(self, obj):
        return serialize_product_payload(obj.product)

class WishlistSerializer(serializers.ModelSerializer):
    """Сериализатор для списка избранного"""
    items = WishlistItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()

    class Meta:
        model = Wishlist
        fields = ['id', 'items', 'total_items', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_total_items(self, obj):
        return obj.total_items

class OrderItemSerializer(serializers.ModelSerializer):
    """Сериализатор для позиции заказа"""
    product_name = serializers.CharField(read_only=True)
    product_image = serializers.SerializerMethodField()
    product_type = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'perfume', 'pigment', 'product_name', 'product_sku', 'quantity',
                 'unit_price', 'total_price', 'product_image', 'product_type']
        read_only_fields = ['id']

    def get_product_image(self, obj):
        if obj.perfume and obj.perfume.image:
            return obj.perfume.image.url
        elif obj.pigment and obj.pigment.image:
            return obj.pigment.image.url
        return None

    def get_product_type(self, obj):
        return obj.product_type

class OrderSerializer(serializers.ModelSerializer):
    """Сериализатор для заказа"""
    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'status', 'payment_method', 'delivery_address',
                 'delivery_city', 'delivery_postal_code', 'delivery_phone',
                 'subtotal', 'delivery_cost', 'total', 'items', 'created_at',
                 'updated_at', 'paid_at', 'shipped_at', 'delivered_at',
                 'customer_notes', 'admin_notes']
        read_only_fields = ['id', 'user', 'subtotal', 'total', 'created_at',
                           'updated_at', 'paid_at', 'shipped_at', 'delivered_at']

class OrderCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания заказа"""
    items = serializers.ListField(write_only=True, required=False)
    delivery_method = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Order
        fields = ['payment_method', 'delivery_address', 'delivery_city',
                 'delivery_postal_code', 'delivery_phone', 'delivery_method',
                 'delivery_cost', 'customer_notes', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items', None)
        user = self.context['request'].user

        # Если items не указаны, берем все из корзины
        if items_data is None:
            try:
                cart = Cart.objects.get(user=user)
                items_data = [{'cart_item': item, 'quantity': item.quantity} for item in cart.items.all()]
            except Cart.DoesNotExist:
                raise serializers.ValidationError("Корзина пуста")
        
        if not items_data:
            raise serializers.ValidationError("Заказ не может быть пустым")

        # Создаем заказ
        subtotal = 0
        order_items = []

        # Вычисляем сумму и создаем позиции заказа
        for item_data in items_data:
            # Поддерживаем два формата: с cart_item_id и с объектом cart_item
            if 'cart_item' in item_data:
                cart_item = item_data['cart_item']
                quantity = item_data['quantity']
            else:
                cart_item_id = item_data.get('cart_item_id')
                quantity = item_data.get('quantity', 1)
                
                try:
                    cart_item = CartItem.objects.get(id=cart_item_id, cart__user=user)
                except CartItem.DoesNotExist:
                    raise serializers.ValidationError(f"Элемент корзины {cart_item_id} не найден")

            if quantity > cart_item.quantity:
                raise serializers.ValidationError(f"Недостаточно товара {cart_item.product.name}")
            
            # Проверяем наличие на складе
            product = cart_item.product
            if not product.in_stock:
                raise serializers.ValidationError(f"Товар {product.name} нет в наличии")
            
            if product.stock_quantity < quantity:
                raise serializers.ValidationError(
                    f"Товар {product.name}: недостаточно на складе (доступно: {product.stock_quantity})"
                )

            # Создаем позицию заказа
            order_item = OrderItem(
                perfume=cart_item.perfume,
                pigment=cart_item.pigment,
                product_name=cart_item.product.name,
                product_sku=getattr(cart_item.product, 'sku', ''),
                quantity=quantity,
                unit_price=cart_item.unit_price,
                total_price=cart_item.unit_price * quantity
            )
            order_items.append((order_item, cart_item, product))
            subtotal += order_item.total_price

        # Создаем заказ
        order = Order.objects.create(user=user, subtotal=subtotal, **validated_data)

        # Сохраняем позиции заказа и обновляем остатки
        for order_item, cart_item, product in order_items:
            order_item.order = order
            order_item.save()
            
            # Уменьшаем количество на складе
            product.stock_quantity -= order_item.quantity
            if product.stock_quantity == 0:
                product.in_stock = False
            product.save()
            
            # Уменьшаем количество в корзине
            cart_item.quantity -= order_item.quantity
            if cart_item.quantity <= 0:
                cart_item.delete()
            else:
                cart_item.save()

        # Отправляем email подтверждение
        from .emails import send_order_confirmation
        send_order_confirmation(order)

        return order
