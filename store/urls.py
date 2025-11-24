from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()
router.register(r'brands', views.BrandViewSet)
router.register(r'categories', views.CategoryViewSet)
router.register(r'perfumes', views.PerfumeViewSet)
router.register(r'pigments', views.PigmentViewSet)
router.register(r'cart-items', views.CartItemViewSet)
router.register(r'orders', views.OrderViewSet)

urlpatterns = [
    path('api/', include(router.urls)),

    # Аутентификация
    path('api/auth/register/', views.UserRegistrationView.as_view(), name='user-register'),
    path('api/auth/login/', views.CustomTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # Профиль пользователя
    path('api/auth/profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('api/auth/settings/', views.UserSettingsView.as_view(), name='user-settings'),

    # Корзина
    path('api/cart/', views.CartView.as_view(), name='cart'),

    # Тема
    path('api/theme/', views.theme_settings, name='theme-settings'),
    path('api/theme/public/', views.public_theme_settings, name='public-theme-settings'),

    # Email OTP
    path('api/auth/otp/send/', views.EmailOTPSendView.as_view(), name='email-otp-send'),
    path('api/auth/otp/verify/', views.EmailOTPVerifyView.as_view(), name='email-otp-verify'),

    # Google OAuth
    path('api/auth/google/login/', views.google_oauth_login, name='google-oauth-login'),
    path('api/auth/google/register/', views.google_oauth_register, name='google-oauth-register'),
    
    # Payment providers
    path('api/payments/yookassa/create/', views.create_yookassa_payment, name='create-yookassa-payment'),
    path('api/payments/yookassa/webhook/', views.yookassa_webhook, name='yookassa-webhook'),
    path('api/payments/yookassa/status/<str:payment_id>/', views.check_yookassa_payment_status, name='check-yookassa-payment-status'),
    
    path('api/payments/tinkoff/create/', views.create_tinkoff_payment, name='create-tinkoff-payment'),
    path('api/payments/tinkoff/notification/', views.tinkoff_notification, name='tinkoff-notification'),
    path('api/payments/tinkoff/status/<str:payment_id>/', views.check_tinkoff_payment_status, name='check-tinkoff-payment-status'),
    
    # Delivery providers
    path('api/delivery/calculate/', views.calculate_delivery_cost, name='calculate-delivery-cost'),
    path('api/delivery/create/', views.create_delivery_order, name='create-delivery-order'),
    path('api/delivery/tracking/<str:tracking_number>/', views.get_tracking_info, name='get-tracking-info'),
    
    # Cart sync
    path('api/cart/sync/', views.sync_cart, name='sync-cart'),
]
