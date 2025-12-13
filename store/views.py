from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
import random
import requests
import jwt
from django.conf import settings
from rest_framework.views import APIView
try:
    from django_filters.rest_framework import DjangoFilterBackend
    from django_filters import FilterSet, NumberFilter, CharFilter
except ImportError:
    # Fallback if django-filter is not installed
    DjangoFilterBackend = None
    FilterSet = None
    NumberFilter = None
    CharFilter = None
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.utils import IntegrityError
from django.shortcuts import get_object_or_404
import logging
from .models import (
    Brand,
    Category,
    Perfume,
    Pigment,
    Promotion,
    TrendingProduct,
    UserProfile,
    UserSettings,
    Cart,
    CartItem,
    Order,
    OrderItem,
    EmailOTP,
    Wishlist,
    WishlistItem,
    LoyaltyAccount,
    LoyaltyTransaction,
    VolumeOption,
    WeightOption,
)
from .serializers import (
    BrandSerializer, CategorySerializer,
    PerfumeSerializer, PerfumeListSerializer,
    PigmentSerializer, PigmentListSerializer,
    PromotionSerializer,
    TrendingProductSerializer,
    UserRegistrationSerializer, UserSerializer, CustomTokenObtainPairSerializer,
    UserProfileSerializer, UserSettingsSerializer,
    CartSerializer, CartItemSerializer, OrderSerializer, OrderCreateSerializer,
    EmailOTPSerializer, EmailOTPVerifySerializer,
    WishlistSerializer, WishlistItemSerializer,
    LoyaltyAccountSerializer, LoyaltyTransactionSerializer,
)

logger = logging.getLogger(__name__)


def debug_log(*args):
    """Безопасный лог для dev: отключен в проде."""
    if settings.DEBUG:
        logger.debug(" ".join(str(a) for a in args))


# Подменяем print внутри модуля, чтобы не светить данные в проде
print = debug_log  # type: ignore

class BrandViewSet(viewsets.ModelViewSet):
    """ViewSet для брендов"""
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [AllowAny]  # Публичный доступ
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'country']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Возвращает только бренды, которые используются в товарах"""
        queryset = super().get_queryset()
        product_type = self.request.query_params.get('product_type')

        if product_type == 'perfume':
            # Только бренды, которые используются в парфюмах
            used_brand_ids = Perfume.objects.values_list('brand_id', flat=True).distinct()
            queryset = queryset.filter(id__in=used_brand_ids)
        elif product_type == 'pigment':
            # Только бренды, которые используются в пигментах
            used_brand_ids = Pigment.objects.values_list('brand_id', flat=True).distinct()
            queryset = queryset.filter(id__in=used_brand_ids)

        return queryset

class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet для категорий"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]  # Публичный доступ
    filter_backends = ([DjangoFilterBackend] if DjangoFilterBackend else []) + [SearchFilter, OrderingFilter]
    filterset_fields = ['category_type']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['category_type', 'name']

    def get_queryset(self):
        """Возвращает только категории, которые используются в товарах"""
        queryset = super().get_queryset()
        category_type = self.request.query_params.get('category_type')

        if category_type == 'perfume':
            # Только категории, которые используются в парфюмах
            used_category_ids = Perfume.objects.values_list('category_id', flat=True).distinct()
            queryset = queryset.filter(id__in=used_category_ids, category_type='perfume')
        elif category_type == 'pigment':
            # Только категории, которые используются в пигментах
            used_category_ids = Pigment.objects.values_list('category_id', flat=True).distinct()
            queryset = queryset.filter(id__in=used_category_ids, category_type='pigment')

        return queryset


class PromotionViewSet(viewsets.ModelViewSet):
    """Акции с поддержкой слотов главной и применением скидок."""
    queryset = Promotion.objects.prefetch_related(
        'perfumes__brand', 'perfumes__category',
        'pigments__brand', 'pigments__category'
    ).all()
    serializer_class = PromotionSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        slot = self.request.query_params.get('slot')
        active = self.request.query_params.get('active')
        if slot:
            qs = qs.filter(slot=slot)
        if active is not None:
            if str(active).lower() in ('1', 'true', 'yes'):
                qs = qs.filter(active=True)
            elif str(active).lower() in ('0', 'false', 'no'):
                qs = qs.filter(active=False)
        return qs.order_by('priority', '-created_at')

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def activate(self, request, pk=None):
        promo = self.get_object()
        promo.apply_discounts()
        serializer = self.get_serializer(promo)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def deactivate(self, request, pk=None):
        promo = self.get_object()
        promo.clear_discounts()
        serializer = self.get_serializer(promo)
        return Response(serializer.data)


class TrendingListView(APIView):
    """Публичный список 'В тренде сейчас'."""
    permission_classes = [AllowAny]

    def get(self, request):
        items = TrendingProduct.objects.select_related('perfume__brand', 'perfume__category',
                                                       'pigment__brand', 'pigment__category').order_by('position', '-created_at')
        serializer = TrendingProductSerializer(items, many=True)
        return Response(serializer.data)


# Кастомный фильтр для парфюмов
if FilterSet:
    class PerfumeFilter(FilterSet):
        min_price = NumberFilter(field_name='price', lookup_expr='gte')
        max_price = NumberFilter(field_name='price', lookup_expr='lte')
        search = CharFilter(method='filter_search')
        on_sale = CharFilter(method='filter_on_sale')

        class Meta:
            model = Perfume
            fields = ['brand', 'category', 'gender', 'in_stock', 'featured', 'on_sale', 'min_price', 'max_price']

        def filter_search(self, queryset, name, value):
            if not value:
                return queryset
            return queryset.filter(
                models.Q(name__icontains=value) |
                models.Q(brand__name__icontains=value) |
                models.Q(category__name__icontains=value) |
                models.Q(description__icontains=value)
            )

        def filter_on_sale(self, queryset, name, value):
            if value in (None, ''):
                return queryset
            if str(value).lower() in ('1', 'true', 'yes'):
                return queryset.filter(
                    models.Q(discount_percentage__gt=0)
                    | models.Q(discount_price__isnull=False, discount_price__gt=0)
                )
            return queryset

class PerfumeViewSet(viewsets.ModelViewSet):
    """ViewSet для парфюмов"""
    queryset = Perfume.objects.select_related('brand', 'category').all()
    permission_classes = [AllowAny]  # Публичный доступ
    filter_backends = ([DjangoFilterBackend] if DjangoFilterBackend else []) + [SearchFilter, OrderingFilter]
    filterset_class = PerfumeFilter if FilterSet else None
    filterset_fields = ['brand', 'category', 'gender', 'in_stock', 'featured'] if not FilterSet else None
    search_fields = ['name', 'brand__name', 'category__name', 'description']
    ordering_fields = ['price', 'created_at', 'name', 'brand__name']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return PerfumeListSerializer
        return PerfumeSerializer

    @action(detail=False, methods=['get'], url_path='by-slug/(?P<slug>[^/]+)')
    def by_slug(self, request, slug=None):
        """Получить парфюм по slug."""
        qs = self.get_queryset().filter(slug=slug).first()
        if not qs:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(qs)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def in_stock(self, request):
        """Получить только товары в наличии"""
        queryset = self.get_queryset().filter(in_stock=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Получить рекомендуемые товары"""
        queryset = self.get_queryset().filter(featured=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_brand(self, request):
        """Получить товары по бренду"""
        brand_id = request.query_params.get('brand_id')
        if not brand_id:
            return Response(
                {'error': 'Необходимо указать brand_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(brand_id=brand_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Получить товары по категории"""
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response(
                {'error': 'Необходимо указать category_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(category_id=category_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PigmentViewSet(viewsets.ModelViewSet):
    """ViewSet для пигментов"""
    queryset = Pigment.objects.select_related('brand', 'category').all()
    permission_classes = [AllowAny]  # Публичный доступ
    filter_backends = ([DjangoFilterBackend] if DjangoFilterBackend else []) + [SearchFilter, OrderingFilter]
    filterset_fields = ['brand', 'category', 'color_type', 'application_type', 'in_stock', 'featured']
    search_fields = ['name', 'brand__name', 'category__name', 'description', 'color_code']
    ordering_fields = ['price', 'created_at', 'name', 'brand__name']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return PigmentListSerializer
        return PigmentSerializer

    @action(detail=False, methods=['get'], url_path='by-slug/(?P<slug>[^/]+)')
    def by_slug(self, request, slug=None):
        """Получить пигмент по slug."""
        qs = self.get_queryset().filter(slug=slug).first()
        if not qs:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(qs)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def in_stock(self, request):
        """Получить только товары в наличии"""
        queryset = self.get_queryset().filter(in_stock=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Получить рекомендуемые товары"""
        queryset = self.get_queryset().filter(featured=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_brand(self, request):
        """Получить товары по бренду"""
        brand_id = request.query_params.get('brand_id')
        if not brand_id:
            return Response(
                {'error': 'Необходимо указать brand_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(brand_id=brand_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Получить товары по категории"""
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response(
                {'error': 'Необходимо указать category_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(category_id=category_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

# Пользовательские представления

class UserRegistrationView(generics.CreateAPIView):
    """Представление для регистрации пользователя"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Автоматически логиним пользователя после регистрации
        refresh = CustomTokenObtainPairSerializer.get_token(user)
        access_token = str(refresh.access_token)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': access_token,
            },
            'message': 'Пользователь успешно зарегистрирован'
        }, status=status.HTTP_201_CREATED)

class CustomTokenObtainPairView(TokenObtainPairView):
    """Кастомное представление для получения JWT токенов"""
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        identifier = request.data.get('username') or request.data.get('email') or '<unknown>'
        logger.info('AUTH_ATTEMPT username_or_email=%s ip=%s', identifier, request.META.get('REMOTE_ADDR'))
        try:
            response = super().post(request, *args, **kwargs)
            logger.info('AUTH_SUCCESS username_or_email=%s status=%s', identifier, response.status_code)
            return response
        except Exception as exc:
            logger.warning('AUTH_FAILED username_or_email=%s reason=%s', identifier, exc)
            raise

class UserProfileView(generics.RetrieveUpdateAPIView):
    """Представление для профиля пользователя"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        print(f"[PROFILE_UPDATE] Request data: {request.data}")  # Логирование
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # Всегда делаем partial=True для обновления профиля
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        print(f"[PROFILE_UPDATE] Serializer is valid: {serializer.is_valid()}")  # Логирование
        if not serializer.is_valid():
            print(f"[PROFILE_UPDATE] Serializer errors: {serializer.errors}")  # Логирование
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        self.perform_update(serializer)
        print(f"[PROFILE_UPDATE] Update successful")  # Логирование

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, use the
            # prefetched cache of related objects
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

class UserSettingsView(generics.RetrieveUpdateAPIView):
    """Представление для настроек пользователя"""
    serializer_class = UserSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user.settings

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data)

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для всех продуктов (парфюмы + пигменты)"""
    permission_classes = [AllowAny]  # Публичный доступ
    filter_backends = ([DjangoFilterBackend] if DjangoFilterBackend else []) + [SearchFilter, OrderingFilter]
    filterset_fields = ['brand', 'category', 'in_stock'] if not FilterSet else None
    search_fields = ['name', 'brand__name', 'category__name', 'description']
    ordering_fields = ['price', 'created_at', 'name', 'brand__name']
    ordering = ['-created_at']

    def get_queryset(self):
        """Возвращаем пустой queryset, так как используем кастомный list метод"""
        return Perfume.objects.none()

    def get_serializer_class(self):
        # Для простоты используем PerfumeListSerializer, но нужно создать универсальный
        return PerfumeListSerializer

    def list(self, request, *args, **kwargs):
        """Получить список всех продуктов"""
        # Получаем все парфюмы
        perfumes = Perfume.objects.select_related('brand', 'category').filter(in_stock=True)
        # Получаем все пигменты
        pigments = Pigment.objects.select_related('brand', 'category').filter(in_stock=True)

        # Применяем фильтры к обоим queryset'ам
        brand = request.query_params.get('brand')
        category = request.query_params.get('category')
        search = request.query_params.get('search')

        if brand:
            perfumes = perfumes.filter(brand=brand)
            pigments = pigments.filter(brand=brand)

        if category:
            perfumes = perfumes.filter(category=category)
            pigments = pigments.filter(category=category)

        if search:
            from django.db.models import Q
            perfumes = perfumes.filter(
                Q(name__icontains=search) |
                Q(brand__name__icontains=search) |
                Q(category__name__icontains=search) |
                Q(description__icontains=search)
            )
            pigments = pigments.filter(
                Q(name__icontains=search) |
                Q(brand__name__icontains=search) |
                Q(category__name__icontains=search) |
                Q(description__icontains=search)
            )

        # Объединяем результаты в один список
        products = []

        # Преобразуем парфюмы в общий формат
        for perfume in perfumes:
            products.append({
                'id': f'perfume_{perfume.id}',  # Уникальный id с типом продукта
                'original_id': perfume.id,  # Сохраняем оригинальный id для ссылок
                'name': perfume.name,
                'brand_name': perfume.brand.name,
                'category_name': perfume.category.name,
                'price': perfume.price,
                'final_price': perfume.get_discounted_price(),
                'is_on_sale': perfume.is_on_sale(),
                'discount_percent_display': perfume.get_discount_percentage_display(),
                'in_stock': perfume.in_stock,
                'image': perfume.image.url if perfume.image else None,
                'product_type': 'perfume',
                'gender': perfume.get_gender_display(),
                'volume_ml': perfume.volume_ml,
            })

        # Преобразуем пигменты в общий формат
        for pigment in pigments:
            products.append({
                'id': f'pigment_{pigment.id}',  # Уникальный id с типом продукта
                'original_id': pigment.id,  # Сохраняем оригинальный id для ссылок
                'name': pigment.name,
                'brand_name': pigment.brand.name,
                'category_name': pigment.category.name,
                'price': pigment.price,
                'final_price': pigment.get_discounted_price(),
                'is_on_sale': pigment.is_on_sale(),
                'discount_percent_display': pigment.get_discount_percentage_display(),
                'in_stock': pigment.in_stock,
                'image': pigment.image.url if pigment.image else None,
                'product_type': 'pigment',
                'color_type': pigment.get_color_type_display(),
                'weight_gr': pigment.weight_gr,
            })

        # Применяем сортировку
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering == 'price':
            products.sort(key=lambda x: x['price'])
        elif ordering == '-price':
            products.sort(key=lambda x: x['price'], reverse=True)
        elif ordering == 'name':
            products.sort(key=lambda x: x['name'])
        elif ordering == '-name':
            products.sort(key=lambda x: x['name'], reverse=True)
        else:  # -created_at or other
            # Для простоты оставляем порядок как есть (можно улучшить)
            pass

        # Пагинация
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        paginator.page_size = request.query_params.get('page_size', 20)

        paginated_products = paginator.paginate_queryset(products, request)

        return paginator.get_paginated_response(paginated_products)

# Представления для магазина

class CartView(generics.RetrieveAPIView):
    """Представление для корзины пользователя"""
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        cart, created = Cart.objects.get_or_create(user=self.request.user)
        print(f"CartView GET for user {self.request.user.username}: created={created}, items={cart.items.count()}")
        return cart

class CartItemViewSet(viewsets.ModelViewSet):
    """ViewSet для элементов корзины"""
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]
    queryset = CartItem.objects.all()  # Базовый queryset, фильтрация будет в get_queryset

    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user)

    def perform_create(self, serializer):
        cart, created = Cart.objects.get_or_create(user=self.request.user)
        serializer.save(cart=cart)

    @action(detail=False, methods=['post'])
    def add_product(self, request):
        """Добавить продукт в корзину"""
        logger = logging.getLogger(__name__)

        product_type = request.data.get('product_type')  # 'perfume' или 'pigment'
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)
        volume_option_id = request.data.get('volume_option_id')
        weight_option_id = request.data.get('weight_option_id')

        logger.info(f"Пользователь {request.user.id} пытается добавить товар: product_type={product_type}, product_id={product_id}, quantity={quantity}, vol={volume_option_id}, wgt={weight_option_id}")

        if not product_type or not product_id:
            logger.warning(f"Пользователь {request.user.id}: отсутствуют обязательные параметры - product_type={product_type}, product_id={product_id}")
            return Response(
                {'error': 'Необходимо указать product_type и product_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Получаем продукт и проверяем его наличие
        try:
            if product_type == 'perfume':
                logger.info(f"Пользователь {request.user.id}: получение парфюма с id={product_id}")
                product = Perfume.objects.get(id=product_id)
            elif product_type == 'pigment':
                logger.info(f"Пользователь {request.user.id}: получение пигмента с id={product_id}")
                product = Pigment.objects.get(id=product_id)
            else:
                logger.error(f"Пользователь {request.user.id}: неверный тип продукта - {product_type}")
                return Response(
                    {'error': 'Неверный тип продукта'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (Perfume.DoesNotExist, Pigment.DoesNotExist):
            logger.error(f"Пользователь {request.user.id}: продукт типа '{product_type}' с id={product_id} не найден в базе данных")
            return Response(
                {'error': 'Продукт не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Обработка вариантов (объем/вес)
        volume_option = None
        weight_option = None
        stock_quantity = product.stock_quantity
        in_stock = product.in_stock
        product_name = product.name

        if volume_option_id:
            try:
                volume_option = VolumeOption.objects.get(id=volume_option_id, perfume=product)
                stock_quantity = volume_option.stock_quantity
                in_stock = volume_option.in_stock
                product_name = f"{product.name} ({volume_option.volume_ml} мл)"
            except VolumeOption.DoesNotExist:
                return Response({'error': 'Указанный вариант объема не найден'}, status=status.HTTP_400_BAD_REQUEST)

        if weight_option_id:
            try:
                weight_option = WeightOption.objects.get(id=weight_option_id, pigment=product)
                stock_quantity = weight_option.stock_quantity
                in_stock = weight_option.in_stock
                product_name = f"{product.name} ({weight_option.weight_gr} г)"
            except WeightOption.DoesNotExist:
                return Response({'error': 'Указанный вариант веса не найден'}, status=status.HTTP_400_BAD_REQUEST)

        # Проверяем наличие товара на складе
        if not in_stock:
            logger.warning(f"Пользователь {request.user.id}: товар '{product_name}' (id={product_id}) не в наличии (in_stock=False)")
            return Response(
                {'error': f'Товар "{product_name}" нет в наличии'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if stock_quantity < quantity:
            logger.warning(f"Пользователь {request.user.id}: недостаточно товара '{product_name}' на складе (запрошено: {quantity}, доступно: {stock_quantity})")
            return Response(
                {'error': f'Товар "{product_name}": недостаточно на складе (доступно: {stock_quantity})'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Получаем или создаем корзину
        cart, created = Cart.objects.get_or_create(user=request.user)

        # Проверяем, существует ли уже такой товар в корзине
        existing_item = CartItem.objects.filter(
            cart=cart,
            perfume_id=product_id if product_type == 'perfume' else None,
            pigment_id=product_id if product_type == 'pigment' else None,
            volume_option=volume_option,
            weight_option=weight_option
        ).first()

        if existing_item:
            # Проверяем, что общее количество не превышает доступное на складе
            new_quantity = existing_item.quantity + quantity
            if stock_quantity < new_quantity:
                logger.warning(f"Пользователь {request.user.id}: недостаточно товара '{product_name}' для добавления к существующему в корзине (доступно: {stock_quantity}, в корзине уже: {existing_item.quantity}, пытаемся добавить: {quantity})")
                return Response(
                    {'error': f'Товар "{product_name}": недостаточно на складе (доступно: {stock_quantity}, в корзине уже: {existing_item.quantity})'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Увеличиваем количество
            logger.info(f"Пользователь {request.user.id}: обновлено количество товара '{product_name}' в корзине с {existing_item.quantity} до {new_quantity}")
            existing_item.quantity = new_quantity
            existing_item.save()
            serializer = self.get_serializer(existing_item)
            return Response(serializer.data)

        # Создаем новый элемент корзины напрямую
        logger.info(f"Пользователь {request.user.id}: создан новый элемент корзины для товара '{product_name}' (количество: {quantity})")
        cart_item = CartItem.objects.create(
            cart=cart,
            quantity=quantity,
            perfume=product if product_type == 'perfume' else None,
            pigment=product if product_type == 'pigment' else None,
            volume_option=volume_option,
            weight_option=weight_option
        )

        # Возвращаем сериализованные данные
        serializer = self.get_serializer(cart_item)

        logger.info(f"Пользователь {request.user.id}: товар '{product.name}' успешно добавлен в корзину")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def update_quantity(self, request, pk=None):
        """Обновить количество товара в корзине"""
        item = self.get_object()
        quantity = request.data.get('quantity', 1)

        if quantity <= 0:
            item.delete()
            return Response({'message': 'Товар удален из корзины'})

        # Проверяем наличие товара на складе
        product = item.product
        if not product.in_stock:
            return Response(
                {'error': f'Товар "{product.name}" нет в наличии'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if product.stock_quantity < quantity:
            return Response(
                {'error': f'Товар "{product.name}": недостаточно на складе (доступно: {product.stock_quantity})'},
                status=status.HTTP_400_BAD_REQUEST
            )

        item.quantity = quantity
        item.save()

        serializer = self.get_serializer(item)
        return Response(serializer.data)

class WishlistView(generics.RetrieveAPIView):
    """Представление для списка избранного пользователя"""
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        wishlist, created = Wishlist.objects.get_or_create(user=self.request.user)
        return wishlist

class WishlistItemViewSet(viewsets.ModelViewSet):
    """ViewSet для элементов избранного"""
    serializer_class = WishlistItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WishlistItem.objects.filter(wishlist__user=self.request.user)

    def create(self, request, *args, **kwargs):
        product_type = request.data.get('product_type')
        product_id = request.data.get('product_id')

        if not product_type or not product_id:
            return Response(
                {'error': 'Необходимо указать product_type и product_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        wishlist, created = Wishlist.objects.get_or_create(user=request.user)

        item_kwargs = {'wishlist': wishlist}
        if product_type == 'perfume':
            item_kwargs['perfume'] = get_object_or_404(Perfume, id=product_id)
            item_kwargs['pigment'] = None
        elif product_type == 'pigment':
            item_kwargs['pigment'] = get_object_or_404(Pigment, id=product_id)
            item_kwargs['perfume'] = None
        else:
            return Response(
                {'error': 'Недопустимый product_type'},
                status=status.HTTP_400_BAD_REQUEST
            )

        item, created = WishlistItem.objects.get_or_create(**item_kwargs)
        serializer = self.get_serializer(item)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def status(self, request):
        """Проверить, находится ли товар в избранном"""
        product_type = request.query_params.get('product_type')
        product_id = request.query_params.get('product_id')

        if not product_type or not product_id:
            return Response(
                {'error': 'Необходимо указать product_type и product_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        filters = {}
        if product_type == 'perfume':
            filters['perfume_id'] = product_id
        elif product_type == 'pigment':
            filters['pigment_id'] = product_id
        else:
            return Response(
                {'error': 'Недопустимый product_type'},
                status=status.HTTP_400_BAD_REQUEST
            )

        item = self.get_queryset().filter(**filters).first()
        return Response({
            'is_favorite': bool(item),
            'item_id': item.id if item else None,
        })

    @action(detail=False, methods=['delete'], url_path='by-product')
    def remove_by_product(self, request):
        """Удалить товар из избранного по типу и ID"""
        product_type = request.query_params.get('product_type') or request.data.get('product_type')
        product_id = request.query_params.get('product_id') or request.data.get('product_id')

        if not product_type or not product_id:
            return Response(
                {'error': 'Необходимо указать product_type и product_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        filters = {}
        if product_type == 'perfume':
            filters['perfume_id'] = product_id
        elif product_type == 'pigment':
            filters['pigment_id'] = product_id
        else:
            return Response(
                {'error': 'Недопустимый product_type'},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted, _ = self.get_queryset().filter(**filters).delete()
        return Response({'removed': bool(deleted)})

    @action(detail=False, methods=['post'], url_path='bulk-add')
    def bulk_add(self, request):
        """Массовое добавление товаров в избранное (для синхронизации)"""
        items = request.data.get('items', [])
        if not isinstance(items, list):
            return Response({'error': 'items должен быть списком'}, status=status.HTTP_400_BAD_REQUEST)

        wishlist, created = Wishlist.objects.get_or_create(user=request.user)
        created_count = 0

        for item_data in items:
            product_type = item_data.get('product_type')
            product_id = item_data.get('product_id')
            if not product_type or not product_id:
                continue

            item_kwargs = {'wishlist': wishlist}
            try:
                if product_type == 'perfume':
                    item_kwargs['perfume'] = Perfume.objects.get(id=product_id)
                    item_kwargs['pigment'] = None
                elif product_type == 'pigment':
                    item_kwargs['pigment'] = Pigment.objects.get(id=product_id)
                    item_kwargs['perfume'] = None
                else:
                    continue
            except (Perfume.DoesNotExist, Pigment.DoesNotExist):
                continue

            _, created_flag = WishlistItem.objects.get_or_create(**item_kwargs)
            if created_flag:
                created_count += 1

        return Response({'created': created_count})

class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet для заказов"""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all()  # Базовый queryset, фильтрация будет в get_queryset

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items')

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            logger.warning(
                'ORDER_CREATE_INVALID user=%s data=%s errors=%s raw_body=%s',
                request.user,
                request.data,
                getattr(serializer, 'errors', None),
                request.body,
            )
            raise

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        logger.info('ORDER_CREATE_OK user=%s order_id=%s', request.user, serializer.instance.id)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user)
        except Exception as exc:
            # Логируем причину 400/500 при создании заказа
            try:
                from django.forms.utils import ErrorDict, ErrorList
                errors = getattr(exc, 'detail', None) or getattr(exc, 'args', None)
                # Приводим ошибки в читаемый вид
                if isinstance(errors, (ErrorDict, ErrorList, dict, list)):
                    err_repr = str(errors)
                else:
                    err_repr = repr(errors)
            except Exception:
                err_repr = repr(exc)
            logger.error(
                'ORDER_CREATE_SAVE_FAILED user=%s error=%s',
                self.request.user,
                err_repr
            )
            raise

    @action(detail=False, methods=['get'])
    def history(self, request):
        """История заказов пользователя"""
        queryset = self.get_queryset()
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class LoyaltyAccountView(generics.RetrieveAPIView):
    """Баланс программы лояльности текущего пользователя"""
    permission_classes = [IsAuthenticated]
    serializer_class = LoyaltyAccountSerializer

    def get_object(self):
        account, _ = LoyaltyAccount.objects.get_or_create(user=self.request.user)
        return account


class LoyaltyTransactionListView(generics.ListAPIView):
    """История операций по баллам лояльности"""
    permission_classes = [IsAuthenticated]
    serializer_class = LoyaltyTransactionSerializer

    def get_queryset(self):
        return LoyaltyTransaction.objects.filter(user=self.request.user).order_by('-created_at')


# Email OTP endpoints

class EmailOTPSendView(generics.CreateAPIView):
    """Отправка OTP кода на email"""
    serializer_class = EmailOTPSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        purpose = serializer.validated_data.get('purpose', 'login')

        # Простейший rate-limit: не чаще 1 запроса в 60 секунд для одного email/цели
        from datetime import timedelta
        recently_sent = EmailOTP.objects.filter(
            email=email,
            purpose=purpose,
            created_at__gte=timezone.now() - timedelta(seconds=60)
        ).exists()
        if recently_sent:
            return Response(
                {'error': 'Слишком часто. Повторите попытку через минуту.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Для регистрации не создаем пользователя до подтверждения OTP
        # Для входа проверяем существование пользователя
        if purpose == 'login':
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response(
                    {'error': 'Пользователь с таким email не найден'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Для регистрации проверяем, не зарегистрирован ли уже пользователь
        elif purpose == 'register':
            try:
                user = User.objects.get(email=email, is_active=True)
                # Если пользователь уже активен, значит он уже зарегистрирован
                return Response(
                    {'error': 'Аккаунт с таким email уже зарегистрирован'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except User.DoesNotExist:
                # Пользователь не существует или не активен - можно продолжать регистрацию
                pass

        # Собираем данные регистрации для сохранения в OTP
        register_data = None
        if purpose == 'register':
            register_data = {
                'username': request.data.get('username', ''),
                'password': request.data.get('password', ''),
                'first_name': request.data.get('first_name', ''),
                'last_name': request.data.get('last_name', ''),
            }

        # Создаем OTP код с магическим токеном и данными регистрации
        otp_instance = EmailOTP.create_otp(email, purpose, register_data)

        # Отправляем email с кодом и магической ссылкой
        from .emails import send_otp_email
        email_sent = send_otp_email(email, otp_instance.otp_code, purpose, otp_instance.magic_token)

        response_data = {
            'message': f'OTP код отправлен на {email}',
            'expires_in': 600,  # 10 минут
        }
        return Response(response_data, status=status.HTTP_201_CREATED)


class EmailOTPVerifyView(generics.CreateAPIView):
    """Верификация OTP кода"""
    serializer_class = EmailOTPVerifySerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp_code']
        purpose = serializer.validated_data['purpose']

        # Находим OTP код
        try:
            otp_instance = EmailOTP.objects.get(
                email=email,
                otp_code=otp_code,
                purpose=purpose,
                is_used=False
            )
        except EmailOTP.DoesNotExist:
            return Response(
                {'error': 'Неверный OTP код'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверяем срок действия
        if otp_instance.is_expired:
            return Response(
                {'error': 'OTP код истек'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Помечаем код как использованный
        otp_instance.is_used = True
        otp_instance.save()

        if purpose == 'login':
            # Вход пользователя
            try:
                user = User.objects.get(email=email)
                # Активируем пользователя при первом входе через OTP
                if not user.is_active:
                    user.is_active = True
                    user.save()
            except User.DoesNotExist:
                return Response(
                    {'error': 'Пользователь не найден'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Генерируем токены
            refresh = CustomTokenObtainPairSerializer.get_token(user)
            access_token = str(refresh.access_token)

            return Response({
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': access_token,
                },
                'message': 'Вход выполнен успешно'
            }, status=status.HTTP_200_OK)

        elif purpose == 'register':
            # Регистрация нового пользователя - создаем только после подтверждения OTP
            try:
                user = User.objects.get(email=email)
                # Если пользователь уже активен, значит он уже зарегистрирован
                if user.is_active:
                    return Response(
                        {'error': 'Аккаунт с таким email уже зарегистрирован'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                # Если пользователь существует, но не активен - обновляем только данные для входа
                # Обновляем только username и password (данные для входа)
                if 'username' in serializer.validated_data and serializer.validated_data['username']:
                    # Проверяем уникальность username
                    if User.objects.filter(username=serializer.validated_data['username']).exclude(pk=user.pk).exists():
                        return Response(
                            {'error': 'Пользователь с таким именем уже существует'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    user.username = serializer.validated_data['username']

                if 'password' in serializer.validated_data and serializer.validated_data['password']:
                    user.set_password(serializer.validated_data['password'])

                # Активируем пользователя после подтверждения OTP
                user.is_active = True
                user.save()

                # Создаем или обновляем UserProfile (все данные профиля хранятся здесь)
                first_name = serializer.validated_data.get('first_name', '')
                last_name = serializer.validated_data.get('last_name', '')
                
                try:
                    profile, created = UserProfile.objects.update_or_create(
                        user=user,
                        defaults={
                            'first_name': first_name,
                            'last_name': last_name
                        }
                    )
                    # Убеждаемся, что данные сохранены
                    if first_name:
                        profile.first_name = first_name
                    if last_name:
                        profile.last_name = last_name
                    profile.save()
                    logger.info(f"Профиль создан/обновлен для пользователя {user.id}: first_name={profile.first_name}, last_name={profile.last_name}")
                except Exception as e:
                    # Если возникла ошибка, пытаемся получить существующий профиль и обновить его
                    logger.warning(f"Ошибка при создании профиля для пользователя {user.id}: {e}")
                    try:
                        profile = UserProfile.objects.get(user=user)
                        if first_name:
                            profile.first_name = first_name
                        if last_name:
                            profile.last_name = last_name
                        profile.save()
                        logger.info(f"Профиль обновлен для пользователя {user.id}: first_name={profile.first_name}, last_name={profile.last_name}")
                    except UserProfile.DoesNotExist:
                        return Response(
                            {'error': 'Ошибка при создании профиля. Аккаунт уже существует'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                # Создаем или получаем UserSettings
                settings_obj, settings_created = UserSettings.objects.get_or_create(user=user)
                
                # Обновляем объект user, чтобы получить свежие данные профиля
                user.refresh_from_db()
                # Принудительно обновляем связанные объекты профиля
                try:
                    user.profile.refresh_from_db()
                except UserProfile.DoesNotExist:
                    pass
            except User.DoesNotExist:
                # Создаем нового пользователя только с данными для входа (username, email, password)
                username = serializer.validated_data.get('username') or email.split('@')[0] + str(random.randint(1000, 9999))
                while User.objects.filter(username=username).exists():
                    username = email.split('@')[0] + str(random.randint(1000, 9999))

                # Создаем пользователя БЕЗ first_name и last_name (они хранятся только в UserProfile)
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=serializer.validated_data.get('password'),
                    is_active=True  # Активируем сразу, так как OTP уже подтвержден
                )

                # Создаем UserProfile с данными профиля (first_name, last_name хранятся здесь)
                first_name = serializer.validated_data.get('first_name', '')
                last_name = serializer.validated_data.get('last_name', '')
                
                try:
                    profile, created = UserProfile.objects.update_or_create(
                        user=user,
                        defaults={
                            'first_name': first_name,
                            'last_name': last_name
                        }
                    )
                    # Убеждаемся, что данные сохранены
                    if first_name:
                        profile.first_name = first_name
                    if last_name:
                        profile.last_name = last_name
                    profile.save()
                    logger.info(f"Профиль создан/обновлен для пользователя {user.id}: first_name={profile.first_name}, last_name={profile.last_name}")
                except Exception as e:
                    logger.error(f"Ошибка при создании профиля: {e}")
                    # Пытаемся получить существующий профиль и обновить его
                    try:
                        profile = UserProfile.objects.get(user=user)
                        if first_name:
                            profile.first_name = first_name
                        if last_name:
                            profile.last_name = last_name
                        profile.save()
                        logger.info(f"Профиль обновлен для пользователя {user.id}: first_name={profile.first_name}, last_name={profile.last_name}")
                    except UserProfile.DoesNotExist:
                        return Response(
                            {'error': 'Ошибка при создании профиля. Попробуйте еще раз'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

                UserSettings.objects.get_or_create(user=user)
                
                # Обновляем объект user, чтобы получить свежие данные профиля
                user.refresh_from_db()
                # Принудительно обновляем связанные объекты профиля
                try:
                    user.profile.refresh_from_db()
                except UserProfile.DoesNotExist:
                    pass

            # Генерируем токены
            refresh = CustomTokenObtainPairSerializer.get_token(user)
            access_token = str(refresh.access_token)
            
            # Сериализуем пользователя с обновленными данными профиля
            user_data = UserSerializer(user).data
            logger.info(f"Возвращаем данные пользователя после регистрации: profile.first_name={user_data.get('profile', {}).get('first_name')}, profile.last_name={user_data.get('profile', {}).get('last_name')}")

            return Response({
                'user': user_data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': access_token,
                },
                'message': 'Регистрация завершена успешно'
            }, status=status.HTTP_201_CREATED)


class MagicLinkVerifyView(generics.CreateAPIView):
    """Верификация через магическую ссылку"""
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        token = request.data.get('token')
        purpose = request.data.get('purpose', 'login')

        if not token:
            return Response(
                {'error': 'Токен не предоставлен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Находим OTP по magic_token (разрешаем использовать даже если уже использован, если пользователь еще не создан)
        try:
            otp_instance = EmailOTP.objects.get(
                magic_token=token,
                purpose=purpose
            )
        except EmailOTP.DoesNotExist:
            return Response(
                {'error': 'Недействительная или истёкшая ссылка'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверяем срок действия
        if otp_instance.is_expired:
            return Response(
                {'error': 'Срок действия ссылки истёк'},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = otp_instance.email
        
        # Проверяем, не создан ли уже пользователь для этого email (если да, то просто входим)
        if purpose == 'register':
            try:
                user_exists = User.objects.filter(email=email, is_active=True).exists()
                if user_exists:
                    # Пользователь уже создан - просто выполняем вход
                    user = User.objects.get(email=email, is_active=True)
                    refresh = CustomTokenObtainPairSerializer.get_token(user)
                    access_token = str(refresh.access_token)
                    return Response({
                        'user': UserSerializer(user).data,
                        'tokens': {
                            'refresh': str(refresh),
                            'access': access_token,
                        },
                        'message': 'Вход выполнен успешно'
                    }, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                pass

        # Помечаем код как использованный только если пользователь еще не создан
        if not otp_instance.is_used:
            otp_instance.is_used = True
            otp_instance.save()

        if purpose == 'login':
            # Вход пользователя
            try:
                user = User.objects.get(email=email)
                if not user.is_active:
                    user.is_active = True
                    user.save()
            except User.DoesNotExist:
                return Response(
                    {'error': 'Пользователь не найден'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Генерируем токены
            refresh = CustomTokenObtainPairSerializer.get_token(user)
            access_token = str(refresh.access_token)

            return Response({
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': access_token,
                },
                'message': 'Вход выполнен успешно'
            }, status=status.HTTP_200_OK)

        elif purpose == 'register':
            # Для регистрации через magic link логика должна быть такой же, как при верификации OTP
            # Получаем данные для регистрации из БД (register_data) или из запроса (fallback)
            register_data_from_db = None
            if otp_instance.register_data:
                import json
                try:
                    register_data_from_db = json.loads(otp_instance.register_data)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Failed to parse register_data for email {email}")
            
            # Используем данные из БД, если они есть, иначе из запроса
            username = (register_data_from_db.get('username', '') if register_data_from_db else request.data.get('username', '')).strip()
            password = (register_data_from_db.get('password', '') if register_data_from_db else request.data.get('password', '')).strip()
            first_name = (register_data_from_db.get('first_name', '') if register_data_from_db else request.data.get('first_name', '')).strip()
            last_name = (register_data_from_db.get('last_name', '') if register_data_from_db else request.data.get('last_name', '')).strip()
            
            # Логирование для отладки
            logger.info(f"Magic link register: email={email}, username={username}, has_password={bool(password)}, first_name={first_name}, last_name={last_name}, data_from_db={register_data_from_db is not None}")
            
            try:
                user = User.objects.get(email=email)
                # Если пользователь уже активен, значит он уже зарегистрирован
                if user.is_active:
                    # Пользователь уже активен - это просто вход
                    refresh = CustomTokenObtainPairSerializer.get_token(user)
                    access_token = str(refresh.access_token)
                    return Response({
                        'user': UserSerializer(user).data,
                        'tokens': {
                            'refresh': str(refresh),
                            'access': access_token,
                        },
                        'message': 'Вход выполнен успешно'
                    }, status=status.HTTP_200_OK)
                
                # Если пользователь существует, но не активен - обновляем данные и активируем
                if username:
                    # Проверяем уникальность username
                    if User.objects.filter(username=username).exclude(pk=user.pk).exists():
                        return Response(
                            {'error': 'Пользователь с таким именем уже существует'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    user.username = username
                
                if password:
                    user.set_password(password)
                
                # Активируем пользователя после подтверждения через магическую ссылку
                user.is_active = True
                user.save()
                
                # Создаем или обновляем UserProfile (все данные профиля хранятся здесь)
                try:
                    profile, created = UserProfile.objects.update_or_create(
                        user=user,
                        defaults={
                            'first_name': first_name,
                            'last_name': last_name
                        }
                    )
                    # Убеждаемся, что данные сохранены
                    if first_name:
                        profile.first_name = first_name
                    if last_name:
                        profile.last_name = last_name
                    profile.save()
                except Exception as e:
                    # Если возникла ошибка, пытаемся получить существующий профиль и обновить его
                    try:
                        profile = UserProfile.objects.get(user=user)
                        if first_name:
                            profile.first_name = first_name
                        if last_name:
                            profile.last_name = last_name
                        profile.save()
                    except UserProfile.DoesNotExist:
                        return Response(
                            {'error': 'Ошибка при создании профиля. Аккаунт уже существует'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                # Создаем или получаем UserSettings
                UserSettings.objects.get_or_create(user=user)
                
            except User.DoesNotExist:
                # Создаем нового пользователя только с данными для входа (username, email, password)
                # Если username не передан или пустой, генерируем его из email
                if not username or username.strip() == '':
                    base_username = email.split('@')[0]
                    username = base_username + str(random.randint(1000, 9999))
                    while User.objects.filter(username=username).exists():
                        username = base_username + str(random.randint(1000, 9999))
                    logger.info(f"Generated username: {username} (original was empty)")
                else:
                    # Проверяем уникальность username перед созданием
                    if User.objects.filter(username=username).exists():
                        # Если username уже занят, генерируем новый
                        base_username = email.split('@')[0]
                        username = base_username + str(random.randint(1000, 9999))
                        while User.objects.filter(username=username).exists():
                            username = base_username + str(random.randint(1000, 9999))
                        logger.warning(f"Username was taken, generated new: {username}")
                
                # Проверяем, что password передан
                if not password or password.strip() == '':
                    return Response(
                        {'error': 'Пароль обязателен для регистрации'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                logger.info(f"Creating user with username={username}, email={email}, first_name={first_name}, last_name={last_name}")
                
                # Используем транзакцию и обработку IntegrityError для предотвращения гонки
                try:
                    with transaction.atomic():
                        # Создаем пользователя БЕЗ first_name и last_name (они хранятся только в UserProfile)
                        user = User.objects.create_user(
                            username=username,
                            email=email,
                            password=password,
                            is_active=True  # Активируем сразу, так как магическая ссылка уже подтверждена
                        )
                        
                        # Создаем UserProfile с данными профиля (first_name, last_name хранятся здесь)
                        profile, created = UserProfile.objects.update_or_create(
                            user=user,
                            defaults={
                                'first_name': first_name,
                                'last_name': last_name
                            }
                        )
                        # Убеждаемся, что данные сохранены
                        if first_name:
                            profile.first_name = first_name
                        if last_name:
                            profile.last_name = last_name
                        profile.save()
                        
                        UserSettings.objects.get_or_create(user=user)
                except IntegrityError as e:
                    # Если пользователь уже создан другим запросом, получаем его
                    logger.warning(f"IntegrityError during user creation: {e}. Trying to get existing user.")
                    try:
                        # Пытаемся получить пользователя по email (более надежно)
                        user = User.objects.get(email=email)
                        logger.info(f"User already exists, retrieved: {user.username}")
                    except User.DoesNotExist:
                        # Если не нашли по email, пытаемся по username
                        user = User.objects.get(username=username)
                        logger.info(f"User found by username: {user.username}")
                    
                    # Обновляем профиль если нужно
                    profile, created = UserProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'first_name': first_name,
                            'last_name': last_name
                        }
                    )
                    if not created:
                        # Обновляем существующий профиль
                        if first_name:
                            profile.first_name = first_name
                        if last_name:
                            profile.last_name = last_name
                        profile.save()
                    
                    UserSettings.objects.get_or_create(user=user)

            # Генерируем токены
            refresh = CustomTokenObtainPairSerializer.get_token(user)
            access_token = str(refresh.access_token)
            
            user.refresh_from_db()

            return Response({
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': access_token,
                },
                'message': 'Регистрация завершена успешно'
            }, status=status.HTTP_201_CREATED)

        return Response(
            {'error': 'Неизвестная цель верификации'},
            status=status.HTTP_400_BAD_REQUEST
        )


# Google OAuth endpoints

def verify_google_token(token):
    """
    Валидирует Google ID token и возвращает данные пользователя
    """
    try:
        print(f"[GOOGLE_VERIFY] Starting token verification, token length: {len(token) if token else 0}")  # Логирование

        # Получаем публичные ключи Google для валидации
        print("[GOOGLE_VERIFY] Fetching Google certificates...")  # Логирование
        response = requests.get('https://www.googleapis.com/oauth2/v3/certs')
        if response.status_code != 200:
            print(f"[GOOGLE_VERIFY] Failed to get Google certs, status: {response.status_code}")  # Логирование
            raise ValueError('Не удалось получить публичные ключи Google')

        certs = response.json()
        print(f"[GOOGLE_VERIFY] Got {len(certs.get('keys', []))} certificates")  # Логирование

        # Декодируем JWT без валидации для получения header
        print("[GOOGLE_VERIFY] Decoding JWT header...")  # Логирование
        header = jwt.get_unverified_header(token)
        kid = header.get('kid')
        print(f"[GOOGLE_VERIFY] Token kid: {kid}")  # Логирование

        if not kid:
            print("[GOOGLE_VERIFY] Error: No kid in JWT header")  # Логирование
            raise ValueError('Неверный JWT token header')

        # Находим соответствующий ключ
        public_key = None
        for cert in certs['keys']:
            if cert['kid'] == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(cert)
                break

        if not public_key:
            print(f"[GOOGLE_VERIFY] Error: No matching public key for kid {kid}")  # Логирование
            raise ValueError('Не найден соответствующий публичный ключ')

        print(f"[GOOGLE_VERIFY] Found matching public key, verifying with audience: {settings.GOOGLE_CLIENT_ID}")  # Логирование

        # Валидируем токен
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience=settings.GOOGLE_CLIENT_ID,
            issuer='https://accounts.google.com'
        )

        print("[GOOGLE_VERIFY] Token verification successful")  # Логирование
        return payload

    except jwt.ExpiredSignatureError as e:
        print(f"[GOOGLE_VERIFY] Token expired: {str(e)}")  # Логирование
        raise ValueError('Токен истек')
    except jwt.InvalidTokenError as e:
        print(f"[GOOGLE_VERIFY] Invalid token: {str(e)}")  # Логирование
        raise ValueError(f'Неверный токен: {str(e)}')
    except Exception as e:
        print(f"[GOOGLE_VERIFY] General error: {str(e)}")  # Логирование
        raise ValueError(f'Ошибка валидации токена: {str(e)}')

def _process_google_oauth(google_token, is_register=False):
    """
    Вспомогательная функция для обработки Google OAuth логина/регистрации
    Принимает токен напрямую, возвращает Response объект
    """
    print(f"[GOOGLE_OAUTH] Google token present: {bool(google_token)}")  # Логирование

    if not google_token:
        print("[GOOGLE_OAUTH] Error: Google token is missing")  # Логирование
        return Response(
            {'error': 'Google токен обязателен'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        print("[GOOGLE_OAUTH] Starting Google token verification...")  # Логирование
        # Валидируем Google ID token
        google_payload = verify_google_token(google_token)
        print(f"[GOOGLE_OAUTH] Google payload: {google_payload}")  # Логирование

        email = google_payload.get('email')
        name = google_payload.get('name', '')
        google_sub = google_payload.get('sub')  # Уникальный ID пользователя Google

        print(f"[GOOGLE_OAUTH] Extracted email: {email}, name: {name}")  # Логирование

        if not email:
            print("[GOOGLE_OAUTH] Error: Email not found in Google token")  # Логирование
            return Response(
                {'error': 'Email не найден в Google токене'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ищем или создаем пользователя по email
        user_created = False
        try:
            user = User.objects.get(email=email)
            print(f"[GOOGLE_OAUTH] Existing user found: {user.email}")  # Логирование
            
            # Активируем пользователя при входе через Google, если он был неактивен
            if not user.is_active:
                user.is_active = True
                user.save()
                print(f"[GOOGLE_OAUTH] User {user.email} activated via Google login")  # Логирование
            
            # Если у пользователя нет пароля, генерируем и отправляем его
            if not user.has_usable_password():
                generated_password = generate_random_password(length=12)
                user.set_password(generated_password)
                user.save()
                print(f"[GOOGLE_OAUTH] Generated password for existing user: {user.username}")  # Логирование
                
                # Отправляем пароль на email пользователя
                email_sent = False
                try:
                    email_sent = send_google_password_email(email, generated_password, user.username, name)
                    if email_sent:
                        print(f"[GOOGLE_OAUTH] Password email sent successfully to {email}")  # Логирование
                    else:
                        print(f"[GOOGLE_OAUTH] Failed to send password email to {email} (send_google_password_email returned False)")  # Логирование
                except Exception as e:
                    print(f"[GOOGLE_OAUTH] Exception while sending password email: {str(e)}")  # Логирование
                    import traceback
                    print(f"[GOOGLE_OAUTH] Email error traceback: {traceback.format_exc()}")  # Логирование
                    # Не прерываем процесс, если email не отправился
        except User.DoesNotExist:
            # Создаем нового пользователя БЕЗ first_name и last_name (они хранятся только в UserProfile)
            user_created = True
            print(f"[GOOGLE_OAUTH] Creating new user: {email}")  # Логирование
            username = email.split('@')[0] + str(random.randint(1000, 9999))
            while User.objects.filter(username=username).exists():
                username = email.split('@')[0] + str(random.randint(1000, 9999))

            # Генерируем случайный пароль для пользователя
            generated_password = generate_random_password(length=12)
            print(f"[GOOGLE_OAUTH] Generated password for user: {username}")  # Логирование

            user = User.objects.create_user(
                username=username,
                email=email,
                password=generated_password,
                is_active=True
            )
            
            # Отправляем пароль на email пользователя
            # Отправляем всегда при создании нового пользователя (и при регистрации, и при логине, если пользователь не найден)
            email_sent = False
            try:
                email_sent = send_google_password_email(email, generated_password, username, name)
                if email_sent:
                    print(f"[GOOGLE_OAUTH] Password email sent successfully to {email}")  # Логирование
                else:
                    print(f"[GOOGLE_OAUTH] Failed to send password email to {email} (send_google_password_email returned False)")  # Логирование
            except Exception as e:
                print(f"[GOOGLE_OAUTH] Exception while sending password email: {str(e)}")  # Логирование
                import traceback
                print(f"[GOOGLE_OAUTH] Email error traceback: {traceback.format_exc()}")  # Логирование
                # Не прерываем процесс, если email не отправился

        # Обновляем данные профиля в UserProfile
        # При регистрации (новый пользователь) - заполняем данными из Google
        # При логине (существующий пользователь) - НЕ перезаписываем, только если поля пустые
        if name:
            first_name = name.split()[0] if name else ''
            last_name = ' '.join(name.split()[1:]) if len(name.split()) > 1 else ''
            
            try:
                profile, profile_created = UserProfile.objects.get_or_create(user=user)
                
                # Если пользователь новый (только что создан) - заполняем данными из Google
                # Если пользователь существующий - заполняем только пустые поля
                if user_created:
                    # При регистрации - заполняем данными из Google
                    print(f"[GOOGLE_OAUTH] New user - setting profile data: {first_name} {last_name}")  # Логирование
                    profile.first_name = first_name
                    profile.last_name = last_name
                    profile.save()
                else:
                    # При логине - заполняем только если поля пустые
                    print(f"[GOOGLE_OAUTH] Existing user - updating only empty fields")  # Логирование
                    updated = False
                    if first_name and not profile.first_name:
                        profile.first_name = first_name
                        updated = True
                        print(f"[GOOGLE_OAUTH] Updated empty first_name: {first_name}")  # Логирование
                    if last_name and not profile.last_name:
                        profile.last_name = last_name
                        updated = True
                        print(f"[GOOGLE_OAUTH] Updated empty last_name: {last_name}")  # Логирование
                    if updated:
                        profile.save()
                    else:
                        print(f"[GOOGLE_OAUTH] Profile already has data, skipping update")  # Логирование
                        
            except Exception as e:
                logger.warning(f"Ошибка при обновлении профиля для пользователя {user.id}: {e}")
                # Пытаемся получить существующий профиль и обновить его только если пустые поля
                try:
                    profile = UserProfile.objects.get(user=user)
                    if user_created:
                        # Новый пользователь - заполняем данными
                        if first_name:
                            profile.first_name = first_name
                        if last_name:
                            profile.last_name = last_name
                        profile.save()
                    else:
                        # Существующий пользователь - только пустые поля
                        if first_name and not profile.first_name:
                            profile.first_name = first_name
                        if last_name and not profile.last_name:
                            profile.last_name = last_name
                        profile.save()
                except UserProfile.DoesNotExist:
                    # Профиль не существует - создаем с данными из Google
                    if first_name or last_name:
                        UserProfile.objects.create(
                            user=user,
                            first_name=first_name,
                            last_name=last_name
                        )

        # Обновляем объект user, чтобы получить свежие данные профиля
        user.refresh_from_db()
        try:
            user.profile.refresh_from_db()
        except UserProfile.DoesNotExist:
            pass

        # Генерируем JWT токены
        refresh = CustomTokenObtainPairSerializer.get_token(user)
        access_token = str(refresh.access_token)

        message = 'Регистрация через Google выполнена успешно' if is_register else 'Вход через Google выполнен успешно'
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': access_token,
            },
            'message': message
        }, status=status.HTTP_200_OK)

    except ValueError as e:
        print(f"[GOOGLE_OAUTH] ValueError caught: {str(e)}")  # Логирование
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        print(f"[GOOGLE_OAUTH] Unexpected error: {str(e)}")  # Логирование
        import traceback
        print(f"[GOOGLE_OAUTH] Full traceback: {traceback.format_exc()}")  # Логирование
        return Response(
            {'error': f'Ошибка авторизации: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])  # Отключаем все аутентификационные классы
def google_oauth_login(request):
    """Вход через Google OAuth"""
    print(f"[GOOGLE_OAUTH] Request data: {request.data}")  # Логирование
    google_token = request.data.get('google_token')
    return _process_google_oauth(google_token, is_register=False)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def google_oauth_register(request):
    """Регистрация через Google OAuth"""
    print(f"[GOOGLE_OAUTH] Request data: {request.data}")  # Логирование
    google_token = request.data.get('google_token')
    # Для Google OAuth регистрация аналогична логину - пользователь создается автоматически
    return _process_google_oauth(google_token, is_register=True)


# API для управления темой

@api_view(['GET', 'POST'])
def theme_settings(request):
    """API для получения и обновления темы пользователя"""
    if not request.user.is_authenticated:
        # Для неавторизованных пользователей перенаправляем на публичный эндпоинт
        return public_theme_settings(request)

    user_settings = request.user.settings

    if request.method == 'GET':
        return Response({
            'theme': user_settings.theme,
            'source': 'database'  # Указываем источник темы
        })

    elif request.method == 'POST':
        theme = request.data.get('theme')
        if theme not in ['light', 'dark']:
            return Response(
                {'error': 'Тема должна быть "light" или "dark"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_settings.theme = theme
        user_settings.save()

        return Response({
            'theme': user_settings.theme,
            'message': 'Тема обновлена'
        })

@api_view(['GET'])
@permission_classes([AllowAny])
def public_theme_settings(request):
    """API для получения темы из сессии (для неавторизованных пользователей)"""
    # Для неавторизованных пользователей тема хранится только в localStorage
    # Этот эндпоинт может использоваться для получения темы по умолчанию
    return Response({
        'theme': 'light',  # Тема по умолчанию
        'source': 'default'
    })


# ============================================
# PAYMENT PROVIDERS API
# ============================================

from .payment_providers.yookassa import YooKassaProvider
from .payment_providers.tinkoff import TinkoffProvider
from .payment_config import payment_urls
from .emails import send_payment_confirmation, send_order_confirmation, generate_random_password, send_google_password_email


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_yookassa_payment(request):
    """Создание платежа через ЮKassa"""
    order_id = request.data.get('order_id')
    
    if not order_id:
        logger.warning('YOO_CREATE_NO_ORDER_ID user=%s data=%s', request.user, request.data)
        return Response(
            {'error': 'order_id обязателен'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        logger.warning('YOO_CREATE_ORDER_NOT_FOUND user=%s order_id=%s', request.user, order_id)
        return Response(
            {'error': 'Заказ не найден'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if not settings.YOOKASSA_SHOP_ID or not settings.YOOKASSA_SECRET_KEY:
        logger.error('YOO_CREATE_NO_CREDS user=%s', request.user)
        return Response(
            {'error': 'ЮKassa не настроена на сервере'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Формируем URL возврата
    return_url = payment_urls.get_yookassa_return_url(order.id)
    
    # Создаем платеж
    provider = YooKassaProvider()
    result = provider.create_payment(order, return_url)
    
    if result['success']:
        logger.info('YOO_CREATE_OK user=%s order_id=%s payment_id=%s', request.user, order.id, result['payment_id'])
        # Сохраняем ID платежа
        order.payment_id = result['payment_id']
        order.payment_method = 'yookassa'
        order.save()
        
        return Response({
            'success': True,
            'payment_id': result['payment_id'],
            'confirmation_url': result['confirmation_url']
        })
    else:
        logger.error('YOO_CREATE_FAILED user=%s order_id=%s error=%s', request.user, order.id, result.get('error'))
        return Response(
            {'error': result.get('error', 'Ошибка создания платежа')},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def yookassa_webhook(request):
    """Обработка webhook от ЮKassa"""
    provider = YooKassaProvider()
    result = provider.handle_webhook(request.data)

    if result['success'] and result.get('order_id'):
        try:
            order = Order.objects.get(id=result['order_id'])

            # Обновляем статус заказа независимо от payment_method
            if result['status'] == 'succeeded' and result.get('paid'):
                from django.utils import timezone
                order.status = 'paid'
                order.paid_at = timezone.now()
                order.save()

                # Отправляем email
                send_payment_confirmation(order)
                logger.info('YOO_WEBHOOK_SUCCESS order_id=%s payment_id=%s', order.id, result.get('payment_id'))

        except Order.DoesNotExist:
            logger.warning('YOO_WEBHOOK_ORDER_NOT_FOUND order_id=%s', result.get('order_id'))
        except Exception as e:
            logger.error('YOO_WEBHOOK_ERROR order_id=%s error=%s', result.get('order_id'), str(e))

    return Response({'status': 'ok'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_config(request):
    """Получить текущую конфигурацию платежных URL-адресов"""
    return Response(payment_urls.get_config_summary())


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_payment_config(request):
    """
    Обновить конфигурацию платежных URL-адресов
    Требуется для быстрого переключения между тестовым и продакшен окружениями
    """
    data = request.data

    # Обновляем URL фронтенда
    if 'frontend_url' in data:
        payment_urls.update_frontend_url(data['frontend_url'])

    # Обновляем webhook URL'ы
    webhook_updates = {}
    if 'yookassa_webhook_url' in data:
        webhook_updates['yookassa_url'] = data['yookassa_webhook_url']
    if 'tinkoff_webhook_url' in data:
        webhook_updates['tinkoff_url'] = data['tinkoff_webhook_url']

    if webhook_updates:
        payment_urls.update_webhook_urls(**webhook_updates)

    return Response({
        'success': True,
        'message': 'Конфигурация обновлена',
        'config': payment_urls.get_config_summary()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_yookassa_payment_status(request, payment_id):
    """Проверка статуса платежа ЮKassa"""
    provider = YooKassaProvider()
    result = provider.check_payment_status(payment_id)
    
    if result['success']:
        return Response({
            'success': True,
            'status': result['status'],
            'paid': result['paid']
        })
    else:
        return Response(
            {'error': result.get('error', 'Ошибка проверки статуса')},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_tinkoff_payment(request):
    """Создание платежа через Тинькофф"""
    order_id = request.data.get('order_id')
    
    if not order_id:
        return Response(
            {'error': 'order_id обязателен'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Заказ не найден'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Формируем URL'ы
    success_url = payment_urls.get_tinkoff_success_url()
    fail_url = payment_urls.get_tinkoff_fail_url()
    
    # Создаем платеж
    provider = TinkoffProvider()
    result = provider.init_payment(order, success_url, fail_url)
    
    if result['success']:
        # Сохраняем ID платежа
        order.payment_id = result['payment_id']
        order.payment_method = 'tinkoff'
        order.save()
        
        return Response({
            'success': True,
            'payment_id': result['payment_id'],
            'payment_url': result['payment_url']
        })
    else:
        return Response(
            {'error': result.get('error', 'Ошибка создания платежа')},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def tinkoff_notification(request):
    """Обработка уведомлений от Тинькофф (или YooKassa через Tinkoff)"""
    # Проверяем, это YooKassa данные или Tinkoff
    data = request.data
    result = None

    if 'type' in data and data.get('type') == 'notification' and 'event' in data and 'object' in data:
        # Это YooKassa webhook данные
        payment_obj = data.get('object', {})
        metadata = payment_obj.get('metadata', {})

        result = {
            'success': True,
            'payment_id': payment_obj.get('id'),
            'status': 'CONFIRMED',  # YooKassa 'succeeded' = Tinkoff 'CONFIRMED'
            'order_id': metadata.get('order_id'),
            'amount': float(payment_obj.get('amount', {}).get('value', 0)),
            'success_payment': payment_obj.get('paid', False) and payment_obj.get('status') == 'succeeded'
        }
    else:
        # Это стандартные Tinkoff данные
        provider = TinkoffProvider()
        result = provider.handle_notification(request.data)

    if result['success'] and result.get('order_id'):
        try:
            order = Order.objects.get(id=result['order_id'])

            # Обновляем статус заказа независимо от payment_method
            if result['status'] == 'CONFIRMED' and result.get('success_payment'):
                from django.utils import timezone
                order.status = 'paid'
                order.paid_at = timezone.now()
                order.save()

                # Отправляем email
                send_payment_confirmation(order)
                logger.info('PAYMENT_WEBHOOK_SUCCESS order_id=%s payment_id=%s', order.id, result.get('payment_id'))

        except Order.DoesNotExist:
            logger.warning('PAYMENT_WEBHOOK_ORDER_NOT_FOUND order_id=%s', result.get('order_id'))
        except Exception as e:
            logger.error('PAYMENT_WEBHOOK_ERROR order_id=%s error=%s', result.get('order_id'), str(e))

    return Response('OK')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_tinkoff_payment_status(request, payment_id):
    """Проверка статуса платежа Тинькофф"""
    provider = TinkoffProvider()
    result = provider.get_payment_state(payment_id)
    
    if result['success']:
        return Response({
            'success': True,
            'status': result['status'],
            'order_id': result.get('order_id')
        })
    else:
        return Response(
            {'error': result.get('error', 'Ошибка проверки статуса')},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============================================
# DELIVERY PROVIDERS API
# ============================================

from .delivery_providers.cdek import CDEKProvider
from .delivery_providers.russian_post import RussianPostProvider


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_delivery_cost(request):
    """Расчет стоимости доставки"""
    city = request.data.get('city')
    postal_code = request.data.get('postal_code')
    cart_id = request.data.get('cart_id')
    
    if not city or not postal_code:
        return Response(
            {'error': 'city и postal_code обязательны'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Получаем корзину для расчета веса
    try:
        cart = Cart.objects.get(user=request.user)
        
        # Рассчитываем общий вес
        total_weight = 0
        packages = []
        
        for item in cart.items.all():
            if item.perfume:
                # Предполагаем средний вес парфюма
                weight = item.perfume.volume_ml * 1.2  # примерно 1.2г на мл
                total_weight += weight * item.quantity
            elif item.pigment:
                weight = item.pigment.weight_gr
                total_weight += weight * item.quantity
        
        # Формируем посылки для CDEK (нужны габариты)
        packages = [{
            'weight': int(total_weight),
            'length': 20,
            'width': 15,
            'height': 10
        }]
        
    except Cart.DoesNotExist:
        total_weight = 500  # Вес по умолчанию
        packages = [{
            'weight': 500,
            'length': 20,
            'width': 15,
            'height': 10
        }]
    
    results = {'options': []}
    
    # Расчет через CDEK
    try:
        cdek = CDEKProvider()
        cdek_result = cdek.calculate_delivery('101000', postal_code, packages)
        
        if cdek_result['success']:
            for option in cdek_result['options']:
                results['options'].append({
                    'provider': 'cdek',
                    'provider_name': 'CDEK',
                    'service': option['tariff_name'],
                    'cost': option['delivery_sum'],
                    'period_min': option['period_min'],
                    'period_max': option['period_max'],
                    'currency': 'RUB'
                })
    except Exception as e:
        print(f'CDEK calculation error: {e}')
    
    # Расчет через Почту России
    try:
        russian_post = RussianPostProvider()
        post_result = russian_post.calculate_delivery('101000', postal_code, int(total_weight))
        
        if post_result['success']:
            for option in post_result['options']:
                results['options'].append({
                    'provider': 'russian_post',
                    'provider_name': 'Почта России',
                    'service': option['service_name'],
                    'cost': option['delivery_sum'],
                    'period_min': option['period_min'],
                    'period_max': option['period_max'],
                    'currency': 'RUB'
                })
    except Exception as e:
        print(f'Russian Post calculation error: {e}')
    
    return Response(results)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_delivery_order(request):
    """Создание заказа на доставку"""
    order_id = request.data.get('order_id')
    provider = request.data.get('provider')  # 'cdek' или 'russian_post'
    tariff_code = request.data.get('tariff_code')  # Для CDEK: код тарифа (137, 139 и т.д.)
    
    if not order_id or not provider:
        return Response(
            {'error': 'order_id и provider обязательны'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        order = Order.objects.select_related('user').prefetch_related('items').get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Заказ не найден'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Проверяем, что заказ уже оплачен или в обработке
    if order.status not in ['paid', 'processing']:
        return Response(
            {'error': 'Заказ должен быть оплачен или в обработке для создания доставки'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Проверяем, что заказ на доставку еще не создан
    if order.tracking_number:
        return Response(
            {'error': 'Заказ на доставку уже создан', 'tracking_number': order.tracking_number},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Рассчитываем вес и габариты посылок
    total_weight = 0
    packages = []
    
    for item in order.items.all():
        if item.perfume:
            # Вес парфюма: примерно 1.2г на мл объема
            weight = item.perfume.volume_ml * 1.2
            total_weight += weight * item.quantity
        elif item.pigment:
            weight = item.pigment.weight_gr
            total_weight += weight * item.quantity
    
    # Минимальный вес 100г
    if total_weight < 100:
        total_weight = 100
    
    # Формируем посылки (можно разбить на несколько, если вес большой)
    # Пока делаем одну посылку
    packages = [{
        'weight': int(total_weight),
        'length': 20,  # см
        'width': 15,   # см
        'height': 10   # см
    }]
    
    # Получаем данные пользователя
    user = order.user
    user_name = user.get_full_name() or user.username
    user_email = user.email or ''
    
    # Адрес отправителя (можно вынести в настройки)
    sender_postal_code = '101000'  # Москва
    sender_city = 'Москва'
    sender_address = 'Адрес склада'  # TODO: вынести в настройки
    
    try:
        if provider == 'cdek':
            # Создание заказа в CDEK
            if not tariff_code:
                tariff_code = 137  # По умолчанию "Посылка склад-дверь"
            
            # Подготовка данных для CDEK API
            # Для CDEK нужны коды городов, но можно использовать postal_code
            cdek_order_data = {
                'type': 1,  # Интернет-магазин
                'number': f'ORDER_{order.id}',
                'tariff_code': int(tariff_code),
                'comment': order.customer_notes or f'Заказ #{order.id}',
                'sender': {
                    'company': 'Интернет-магазин парфюмерии',  # TODO: вынести в настройки
                    'name': 'Отдел доставки',
                    'phones': [{'number': '+79991234567'}],  # TODO: вынести в настройки
                    'email': settings.DEFAULT_FROM_EMAIL or 'noreply@example.com'
                },
                'recipient': {
                    'name': user_name,
                    'phones': [{'number': order.delivery_phone}],
                    'email': user_email
                },
                'from_location': {
                    'postal_code': sender_postal_code,
                    'address': sender_address,
                    'city': sender_city
                },
                'to_location': {
                    'postal_code': order.delivery_postal_code,
                    'address': order.delivery_address,
                    'city': order.delivery_city
                },
                'packages': [
                    {
                        'number': f'PACKAGE_{order.id}_1',
                        'weight': pkg['weight'],
                        'length': pkg['length'],
                        'width': pkg['width'],
                        'height': pkg['height'],
                        'comment': 'Парфюмерия'
                    }
                    for pkg in packages
                ]
            }
            
            cdek = CDEKProvider()
            result = cdek.create_order(cdek_order_data)
            
            if result['success']:
                # Сохраняем данные в заказ
                order.tracking_number = result.get('cdek_number', '')
                order.delivery_service_order_id = result.get('order_uuid', '')
                order.status = 'shipped'
                from django.utils import timezone
                order.shipped_at = timezone.now()
                order.save()
                
                # Отправляем email уведомление
                from .emails import send_shipping_notification
                send_shipping_notification(order, order.tracking_number)
                
                return Response({
                    'success': True,
                    'message': 'Заказ на доставку CDEK создан',
                    'tracking_number': order.tracking_number,
                    'order_uuid': result.get('order_uuid'),
                    'cdek_number': result.get('cdek_number')
                })
            else:
                return Response(
                    {'error': result.get('error', 'Ошибка создания заказа в CDEK')},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        elif provider == 'russian_post':
            # Создание заказа в Почте России
            # Определяем тип отправления по весу
            mail_type = 'POSTAL_PARCEL'  # Посылка
            if total_weight > 2000:  # Если больше 2кг, может потребоваться другой тип
                mail_type = 'POSTAL_PARCEL'
            
            # Подготовка данных для Почты России API
            russian_post_order_data = [{
                'mailType': mail_type,
                'mailCategory': 'ORDINARY',  # Обычное отправление
                'weight': int(total_weight),
                'recipientName': user_name,
                'recipientAddress': {
                    'index': order.delivery_postal_code,
                    'address': order.delivery_address,
                    'area': order.delivery_city
                },
                'recipientPhone': order.delivery_phone,
                'senderName': 'Интернет-магазин парфюмерии',  # TODO: вынести в настройки
                'senderAddress': {
                    'index': sender_postal_code,
                    'address': sender_address
                },
                'payment': 0,  # 0 - наложенный платеж (если оплата наличными), 1 - предоплата
                'declaredValue': float(order.total),  # Объявленная ценность
                'orderNum': f'ORDER_{order.id}',
                'comment': order.customer_notes or f'Заказ #{order.id}'
            }]
            
            russian_post = RussianPostProvider()
            result = russian_post.create_order(russian_post_order_data)
            
            if result['success']:
                # Сохраняем данные в заказ
                order.tracking_number = result.get('tracking_number', '')
                order.delivery_service_order_id = result.get('order_id', '')
                order.status = 'shipped'
                from django.utils import timezone
                order.shipped_at = timezone.now()
                order.save()
                
                # Отправляем email уведомление
                from .emails import send_shipping_notification
                send_shipping_notification(order, order.tracking_number)
                
                return Response({
                    'success': True,
                    'message': 'Заказ на доставку Почты России создан',
                    'tracking_number': order.tracking_number,
                    'order_id': result.get('order_id'),
                    'batch_name': result.get('batch_name')
                })
            else:
                return Response(
                    {'error': result.get('error', 'Ошибка создания заказа в Почте России')},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        else:
            return Response(
                {'error': f'Неизвестный провайдер доставки: {provider}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    except Exception as e:
        logging.error(f'Error creating delivery order: {str(e)}', exc_info=True)
        return Response(
            {'error': f'Ошибка создания заказа на доставку: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_tracking_info(request, tracking_number):
    """Получение информации об отслеживании"""
    provider = request.query_params.get('provider')
    
    if not provider:
        return Response(
            {'error': 'provider обязателен'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if provider == 'cdek':
        cdek = CDEKProvider()
        result = cdek.get_tracking_info(tracking_number)
    elif provider == 'russian_post':
        russian_post = RussianPostProvider()
        result = russian_post.get_tracking_info(tracking_number)
    else:
        return Response(
            {'error': 'Неизвестный провайдер доставки'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if result['success']:
        return Response(result)
    else:
        return Response(
            {'error': result.get('error', 'Ошибка получения информации')},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============================================
# CART SYNC API
# ============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_cart(request):
    """Синхронизация корзины клиента с сервером"""
    items = request.data.get('items', [])
    print(f"Sync cart for user {request.user.username}: {len(items)} items")
    print(f"Items data: {items}")

    # Получаем или создаем корзину
    cart, created = Cart.objects.get_or_create(user=request.user)
    print(f"Cart created: {created}, current items: {cart.items.count()}")

    # Создаем словарь текущих элементов корзины для быстрого поиска
    existing_items = {}
    for item in cart.items.all():
        vol_key = f"vol-{item.volume_option_id or 'base'}"
        wgt_key = f"wgt-{item.weight_option_id or 'base'}"
        key = f"{item.product_type}-{item.product.id}-{vol_key}-{wgt_key}"
        existing_items[key] = item

    # Обрабатываем товары из запроса
    for item_data in items:
        product_type = item_data.get('product_type')  # 'perfume' или 'pigment'
        product_id = item_data.get('product_id')
        quantity = item_data.get('quantity', 1)
        volume_option_id = item_data.get('volume_option_id')
        weight_option_id = item_data.get('weight_option_id')

        print(f"Processing item: type={product_type}, id={product_id}, qty={quantity}, vol={volume_option_id}, wgt={weight_option_id}")

        vol_key = f"vol-{volume_option_id or 'base'}"
        wgt_key = f"wgt-{weight_option_id or 'base'}"
        key = f"{product_type}-{product_id}-{vol_key}-{wgt_key}"

        if key in existing_items:
            # Обновляем количество существующего товара
            existing_item = existing_items[key]
            print(f"Updating existing item {existing_item.id}, old qty: {existing_item.quantity}, new qty: {quantity}")

            # Проверяем наличие товара на складе перед обновлением
            product = existing_item.product
            selected_volume = None
            selected_weight = None

            if volume_option_id:
                try:
                    selected_volume = VolumeOption.objects.get(id=volume_option_id, perfume_id=product_id)
                except VolumeOption.DoesNotExist:
                    print(f"Volume option {volume_option_id} not found for product {product_id}")
                    continue

            if weight_option_id:
                try:
                    selected_weight = WeightOption.objects.get(id=weight_option_id, pigment_id=product_id)
                except WeightOption.DoesNotExist:
                    print(f"Weight option {weight_option_id} not found for product {product_id}")
                    continue

            available_stock = (
                selected_volume.stock_quantity if selected_volume else
                selected_weight.stock_quantity if selected_weight else
                product.stock_quantity
            )
            in_stock = (
                selected_volume.in_stock if selected_volume else
                selected_weight.in_stock if selected_weight else
                product.in_stock
            )

            if not in_stock:
                print(f"Product {product.name} is not in stock - removing from cart")
                existing_item.delete()
                del existing_items[key]
                continue

            if available_stock < quantity:
                print(f"Product {product.name} has insufficient stock ({available_stock} < {quantity}) - adjusting quantity")
                existing_item.quantity = available_stock
            else:
                existing_item.quantity = quantity

            # Проставляем вариант, если он изменился
            if selected_volume or selected_weight:
                existing_item.volume_option = selected_volume
                existing_item.weight_option = selected_weight

            try:
                existing_item.save()
                print(f"Successfully saved item {existing_item.id} with quantity {existing_item.quantity}")
            except Exception as e:
                print(f"Error saving item {existing_item.id}: {e}")
            del existing_items[key]  # Удаляем из словаря обработанных
        else:
            # Добавляем новый товар
            print(f"Adding new item: type={product_type}, id={product_id}")
            if product_type == 'perfume':
                try:
                    perfume = Perfume.objects.get(id=product_id)
                    selected_volume = None

                    if volume_option_id:
                        try:
                            selected_volume = VolumeOption.objects.get(id=volume_option_id, perfume=perfume)
                            print(f"Using volume option {selected_volume.id} ({selected_volume.volume_ml} мл) with stock {selected_volume.stock_quantity} / in_stock={selected_volume.in_stock}")
                        except VolumeOption.DoesNotExist as e:
                            print(f"Volume option {volume_option_id} not found for perfume {product_id}: {e}")
                            continue

                    # Проверяем наличие товара на складе
                    in_stock = selected_volume.in_stock if selected_volume else perfume.in_stock
                    stock_qty = selected_volume.stock_quantity if selected_volume else perfume.stock_quantity
                    if not in_stock:
                        print(f"Perfume {perfume.name} is not in stock (variant checked) - skipping")
                        continue
                    if stock_qty < quantity:
                        print(f"Perfume {perfume.name} has insufficient stock ({stock_qty} < {quantity}) - skipping")
                        continue

                    new_item = CartItem.objects.create(
                        cart=cart,
                        perfume=perfume,
                        volume_option=selected_volume,
                        quantity=quantity
                    )
                    print(f"Created cart item: {new_item.id}")
                    # Проверяем, что элемент действительно сохранен
                    saved_item = CartItem.objects.get(id=new_item.id)
                    print(f"Verified saved item: {saved_item.id}, qty: {saved_item.quantity}, vol={saved_item.volume_option_id}")
                except Perfume.DoesNotExist as e:
                    print(f"Perfume {product_id} not found: {e}")
                    pass
                except Exception as e:
                    print(f"Error creating perfume cart item: {e}")
            elif product_type == 'pigment':
                try:
                    pigment = Pigment.objects.get(id=product_id)
                    selected_weight = None

                    if weight_option_id:
                        try:
                            selected_weight = WeightOption.objects.get(id=weight_option_id, pigment=pigment)
                            print(f"Using weight option {selected_weight.id} ({selected_weight.weight_gr} г) with stock {selected_weight.stock_quantity} / in_stock={selected_weight.in_stock}")
                        except WeightOption.DoesNotExist as e:
                            print(f"Weight option {weight_option_id} not found for pigment {product_id}: {e}")
                            continue

                    # Проверяем наличие товара на складе
                    in_stock = selected_weight.in_stock if selected_weight else pigment.in_stock
                    stock_qty = selected_weight.stock_quantity if selected_weight else pigment.stock_quantity
                    if not in_stock:
                        print(f"Pigment {pigment.name} is not in stock - skipping")
                        continue
                    if stock_qty < quantity:
                        print(f"Pigment {pigment.name} has insufficient stock ({stock_qty} < {quantity}) - skipping")
                        continue

                    new_item = CartItem.objects.create(
                        cart=cart,
                        pigment=pigment,
                        weight_option=selected_weight,
                        quantity=quantity
                    )
                    print(f"Created cart item: {new_item.id}")
                except Pigment.DoesNotExist as e:
                    print(f"Pigment {product_id} not found: {e}")
                    pass
                except Exception as e:
                    print(f"Error creating pigment cart item: {e}")
            else:
                print(f"Unknown product type: {product_type}")

    # Удаляем товары, которые не пришли в запросе (были удалены на клиенте)
    print(f"Removing {len(existing_items)} items that are no longer in cart")
    for remaining_item in existing_items.values():
        print(f"Deleting cart item {remaining_item.id}")
        remaining_item.delete()

    # Возвращаем обновленную корзину
    serializer = CartSerializer(cart)
    print(f"Sync completed. Final cart items: {cart.items.count()}")
    print(f"Response data: {serializer.data}")
    return Response(serializer.data)


class ProductBatchDetailView(APIView):
    """
    Получение актуальных данных для списка товаров по их ID.
    Используется для синхронизации цен в корзине.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        perfume_ids = request.data.get('perfumes', [])
        pigment_ids = request.data.get('pigments', [])

        # Валидация входных данных
        if not isinstance(perfume_ids, list) or not isinstance(pigment_ids, list):
            return Response(
                {'error': 'perfumes и pigments должны быть списками'},
                status=status.HTTP_400_BAD_REQUEST
            )

        perfumes = Perfume.objects.filter(id__in=perfume_ids)
        pigments = Pigment.objects.filter(id__in=pigment_ids)

        perfume_serializer = PerfumeListSerializer(perfumes, many=True, context={'request': request})
        pigment_serializer = PigmentListSerializer(pigments, many=True, context={'request': request})

        return Response({
            'perfumes': perfume_serializer.data,
            'pigments': pigment_serializer.data,
        })


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])  # Отключаем аутентификацию
def sync_product_prices(request):
    """Синхронизация цен товаров для корзины"""
    perfume_ids = request.data.get('perfumes', [])
    pigment_ids = request.data.get('pigments', [])

    if not isinstance(perfume_ids, list) or not isinstance(pigment_ids, list):
        return Response(
            {'error': 'perfumes и pigments должны быть списками'},
            status=status.HTTP_400_BAD_REQUEST
        )

    perfumes = Perfume.objects.filter(id__in=perfume_ids)
    pigments = Pigment.objects.filter(id__in=pigment_ids)

    perfume_serializer = PerfumeListSerializer(perfumes, many=True, context={'request': request})
    pigment_serializer = PigmentListSerializer(pigments, many=True, context={'request': request})

    return Response({
        'perfumes': perfume_serializer.data,
        'pigments': pigment_serializer.data,
    })
