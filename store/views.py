from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
import random
import requests
import jwt
from django.conf import settings
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
from django.db import models
from django.shortcuts import get_object_or_404
import logging
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
    Wishlist,
    WishlistItem,
)
from .serializers import (
    BrandSerializer, CategorySerializer,
    PerfumeSerializer, PerfumeListSerializer,
    PigmentSerializer, PigmentListSerializer,
    UserRegistrationSerializer, UserSerializer, CustomTokenObtainPairSerializer,
    UserProfileSerializer, UserSettingsSerializer,
    CartSerializer, CartItemSerializer, OrderSerializer, OrderCreateSerializer,
    EmailOTPSerializer, EmailOTPVerifySerializer,
    WishlistSerializer, WishlistItemSerializer
)

logger = logging.getLogger(__name__)

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

# Кастомный фильтр для парфюмов
if FilterSet:
    class PerfumeFilter(FilterSet):
        min_price = NumberFilter(field_name='price', lookup_expr='gte')
        max_price = NumberFilter(field_name='price', lookup_expr='lte')
        search = CharFilter(method='filter_search')

        class Meta:
            model = Perfume
            fields = ['brand', 'category', 'gender', 'in_stock', 'featured', 'min_price', 'max_price']

        def filter_search(self, queryset, name, value):
            if not value:
                return queryset
            return queryset.filter(
                models.Q(name__icontains=value) |
                models.Q(brand__name__icontains=value) |
                models.Q(category__name__icontains=value) |
                models.Q(description__icontains=value)
            )

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
        product_type = request.data.get('product_type')  # 'perfume' или 'pigment'
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)

        if not product_type or not product_id:
            return Response(
                {'error': 'Необходимо указать product_type и product_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Получаем или создаем корзину
        cart, created = Cart.objects.get_or_create(user=request.user)

        # Проверяем, существует ли уже такой товар в корзине
        existing_item = None
        if product_type == 'perfume':
            existing_item = CartItem.objects.filter(cart=cart, perfume_id=product_id).first()
        elif product_type == 'pigment':
            existing_item = CartItem.objects.filter(cart=cart, pigment_id=product_id).first()

        if existing_item:
            # Увеличиваем количество
            existing_item.quantity += quantity
            existing_item.save()
            serializer = self.get_serializer(existing_item)
            return Response(serializer.data)

        # Создаем новый элемент корзины
        item_data = {'quantity': quantity}
        if product_type == 'perfume':
            item_data['perfume_id'] = product_id
        elif product_type == 'pigment':
            item_data['pigment_id'] = product_id

        serializer = self.get_serializer(data=item_data)
        serializer.is_valid(raise_exception=True)
        serializer.save(cart=cart)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def update_quantity(self, request, pk=None):
        """Обновить количество товара в корзине"""
        item = self.get_object()
        quantity = request.data.get('quantity', 1)

        if quantity <= 0:
            item.delete()
            return Response({'message': 'Товар удален из корзины'})

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

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

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

        # Проверяем, существует ли пользователь для входа
        if purpose == 'login':
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Создаем временного пользователя для входа
                username = email.split('@')[0] + str(random.randint(1000, 9999))
                while User.objects.filter(username=username).exists():
                    username = email.split('@')[0] + str(random.randint(1000, 9999))

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=email.split('@')[0].title(),
                    is_active=False  # Не активируем до подтверждения OTP
                )

        # Создаем OTP код
        otp_instance = EmailOTP.create_otp(email, purpose)

        # Отправляем email с кодом
        from .emails import send_otp_email
        email_sent = send_otp_email(email, otp_instance.otp_code, purpose)

        response_data = {
            'message': f'OTP код отправлен на {email}',
            'expires_in': 600,  # 10 минут
        }
        
        # В режиме отладки или если email не отправлен, возвращаем код в ответе
        if settings.DEBUG or not email_sent:
            response_data['otp_code'] = otp_instance.otp_code
            response_data['debug'] = True

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
            # Регистрация нового пользователя
            try:
                user = User.objects.get(email=email)
                if user.is_active:
                    return Response(
                        {'error': 'Пользователь уже зарегистрирован'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                # Активируем пользователя
                user.is_active = True
                user.save()
            except User.DoesNotExist:
                # Создаем нового пользователя
                username = email.split('@')[0] + str(random.randint(1000, 9999))
                while User.objects.filter(username=username).exists():
                    username = email.split('@')[0] + str(random.randint(1000, 9999))

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=email.split('@')[0].title(),
                    is_active=True
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
                'message': 'Регистрация завершена успешно'
            }, status=status.HTTP_201_CREATED)


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

@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])  # Отключаем все аутентификационные классы
def google_oauth_login(request):
    """Вход через Google OAuth"""
    print(f"[GOOGLE_OAUTH] Request data: {request.data}")  # Логирование
    google_token = request.data.get('google_token')
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
        try:
            user = User.objects.get(email=email)
            # Обновляем данные если нужно
            if name and not user.first_name:
                user.first_name = name.split()[0] if name else ''
                user.last_name = ' '.join(name.split()[1:]) if len(name.split()) > 1 else ''
                user.save()
        except User.DoesNotExist:
            # Создаем нового пользователя
            username = email.split('@')[0] + str(random.randint(1000, 9999))
            while User.objects.filter(username=username).exists():
                username = email.split('@')[0] + str(random.randint(1000, 9999))

            first_name = name.split()[0] if name else ''
            last_name = ' '.join(name.split()[1:]) if len(name.split()) > 1 else ''

            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )

        # Генерируем JWT токены
        refresh = CustomTokenObtainPairSerializer.get_token(user)
        access_token = str(refresh.access_token)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': access_token,
            },
            'message': 'Вход через Google выполнен успешно'
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
@authentication_classes([])
def google_oauth_register(request):
    """Регистрация через Google OAuth"""
    # Для Google OAuth регистрация аналогична логину - пользователь создается автоматически
    return google_oauth_login(request)


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
from .emails import send_payment_confirmation, send_order_confirmation


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_yookassa_payment(request):
    """Создание платежа через ЮKassa"""
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
    
    # Формируем URL возврата
    return_url = request.build_absolute_uri('/payment/callback/')
    
    # Создаем платеж
    provider = YooKassaProvider()
    result = provider.create_payment(order, return_url)
    
    if result['success']:
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
            
            # Обновляем статус заказа
            if result['status'] == 'succeeded' and result.get('paid'):
                from django.utils import timezone
                order.status = 'paid'
                order.paid_at = timezone.now()
                order.save()
                
                # Отправляем email
                send_payment_confirmation(order)
            
        except Order.DoesNotExist:
            pass
    
    return Response({'status': 'ok'})


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
    success_url = request.build_absolute_uri('/payment/success/')
    fail_url = request.build_absolute_uri('/payment/failed/')
    
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
    """Обработка уведомлений от Тинькофф"""
    provider = TinkoffProvider()
    result = provider.handle_notification(request.data)
    
    if result['success'] and result.get('order_id'):
        try:
            order = Order.objects.get(id=result['order_id'])
            
            # Обновляем статус заказа
            if result['status'] == 'CONFIRMED' and result.get('success_payment'):
                from django.utils import timezone
                order.status = 'paid'
                order.paid_at = timezone.now()
                order.save()
                
                # Отправляем email
                send_payment_confirmation(order)
            
        except Order.DoesNotExist:
            pass
    
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
    
    if not order_id or not provider:
        return Response(
            {'error': 'order_id и provider обязательны'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Заказ не найден'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Здесь должна быть логика создания заказа в службе доставки
    # Пока возвращаем заглушку
    
    return Response({
        'success': True,
        'message': 'Заказ на доставку создан',
        'tracking_number': 'TRACK123456789'
    })


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
        key = f"{item.product_type}-{item.product.id}"
        existing_items[key] = item

    # Обрабатываем товары из запроса
    for item_data in items:
        product_type = item_data.get('product_type')  # 'perfume' или 'pigment'
        product_id = item_data.get('product_id')
        quantity = item_data.get('quantity', 1)

        print(f"Processing item: type={product_type}, id={product_id}, qty={quantity}")

        key = f"{product_type}-{product_id}"

        if key in existing_items:
            # Обновляем количество существующего товара
            existing_item = existing_items[key]
            print(f"Updating existing item {existing_item.id}, old qty: {existing_item.quantity}, new qty: {quantity}")
            existing_item.quantity = quantity
            try:
                existing_item.save()
                print(f"Successfully saved item {existing_item.id} with quantity {quantity}")
            except Exception as e:
                print(f"Error saving item {existing_item.id}: {e}")
            del existing_items[key]  # Удаляем из словаря обработанных
        else:
            # Добавляем новый товар
            print(f"Adding new item: type={product_type}, id={product_id}")
            if product_type == 'perfume':
                try:
                    perfume = Perfume.objects.get(id=product_id)
                    print(f"Found perfume: {perfume.name}")
                    new_item = CartItem.objects.create(
                        cart=cart,
                        perfume=perfume,
                        quantity=quantity
                    )
                    print(f"Created cart item: {new_item.id}")
                    # Проверяем, что элемент действительно сохранен
                    saved_item = CartItem.objects.get(id=new_item.id)
                    print(f"Verified saved item: {saved_item.id}, qty: {saved_item.quantity}")
                except Perfume.DoesNotExist as e:
                    print(f"Perfume {product_id} not found: {e}")
                    pass
                except Exception as e:
                    print(f"Error creating perfume cart item: {e}")
            elif product_type == 'pigment':
                try:
                    pigment = Pigment.objects.get(id=product_id)
                    print(f"Found pigment: {pigment.name}")
                    new_item = CartItem.objects.create(
                        cart=cart,
                        pigment=pigment,
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