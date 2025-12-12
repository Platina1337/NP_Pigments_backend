from django.urls import path
from . import views

app_name = "adminpanel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # Каталог
    path("brands/", views.brand_list, name="brand_list"),
    path("brands/create/", views.brand_create, name="brand_create"),
    path("brands/<int:pk>/edit/", views.brand_edit, name="brand_edit"),
    path("brands/<int:pk>/delete/", views.brand_delete, name="brand_delete"),

    path("categories/", views.category_list, name="category_list"),
    path("categories/create/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),

    path("perfumes/", views.perfume_list, name="perfume_list"),
    path("perfumes/create/", views.perfume_create, name="perfume_create"),
    path("perfumes/<int:pk>/edit/", views.perfume_edit, name="perfume_edit"),
    path("perfumes/<int:pk>/delete/", views.perfume_delete, name="perfume_delete"),

    path("pigments/", views.pigment_list, name="pigment_list"),
    path("pigments/create/", views.pigment_create, name="pigment_create"),
    path("pigments/<int:pk>/edit/", views.pigment_edit, name="pigment_edit"),
    path("pigments/<int:pk>/delete/", views.pigment_delete, name="pigment_delete"),

    # Заказы
    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("orders/<int:pk>/status/", views.order_status_update, name="order_status_update"),

    # Пользователи
    path("users/", views.user_list, name="user_list"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/loyalty/", views.user_loyalty_update, name="user_loyalty_update"),

    # Акции и скидки
    path("discounts/", views.discount_list, name="discount_list"),
    path("discounts/manage/", views.discount_manage, name="discount_manage"),
    path("discounts/create/", views.discount_create, name="discount_create"),
    path("discounts/<str:product_type>/<int:pk>/remove/", views.discount_remove, name="discount_remove"),
    path("trending/manage/", views.trending_manage, name="trending_manage"),
    path("images/<int:pk>/delete/", views.product_image_delete, name="product_image_delete"),
]

