from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.files.base import ContentFile
from io import BytesIO
import logging
from functools import wraps
try:
    from PIL import Image
except ImportError:
    Image = None

from store.models import (
    Brand,
    Category,
    Perfume,
    Pigment,
    ProductImage,
    Promotion,
    TrendingProduct,
    Order,
    OrderItem,
    LoyaltyAccount,
    LoyaltyTransaction,
    Wishlist,
    Cart,
    UserProfile,
    UserSettings,
)
from .models import AdminActionLog
from .forms import DiscountBulkForm, PromotionForm
from .forms import (
    BrandForm,
    CategoryForm,
    PerfumeForm,
    PigmentForm,
    ProductImageForm,
    OrderStatusForm,
    LoyaltyAdjustForm,
    UserProfileForm,
    UserSettingsForm,
    UserForm,
    VolumeOptionFormSet,
    WeightOptionFormSet,
)

logger = logging.getLogger(__name__)

# Роль/группа: admin, content_manager, orders_manager
CATALOG_ROLES = {"content_manager", "admin"}
ORDERS_ROLES = {"orders_manager", "admin"}
USERS_ROLES = {"orders_manager", "admin"}


def log_action(request, action: str, obj=None, extra=None):
    """Упрощенный аудит действий в кастомной админке с записью в БД."""
    payload = {
        "user": getattr(request, "user", None),
        "action": action,
    }
    if obj is not None:
        payload["object"] = f"{obj}"
        payload["object_id"] = getattr(obj, "pk", None)
    if extra:
        payload.update(extra)

    logger.info("admin_action", extra=payload)

    try:
        AdminActionLog.objects.create(
            user=getattr(request, "user", None),
            action=action,
            object_repr=payload.get("object", "") or "",
            object_id=str(payload.get("object_id") or ""),
            extra=extra or {},
            ip_address=request.META.get("REMOTE_ADDR"),
        )
    except Exception:
        # В проде не должны падать из-за аудита
        logger.exception("Failed to persist admin action", extra=payload)


def staff_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_staff or u.is_superuser)(view_func))


def role_required(*roles):
    """Проверка групп для разделов админки."""

    def decorator(view_func):
        @wraps(view_func)
        @staff_required
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_superuser or not roles:
                return view_func(request, *args, **kwargs)
            if user.groups.filter(name__in=roles).exists():
                return view_func(request, *args, **kwargs)
            messages.error(request, "Недостаточно прав для этого раздела.")
            return redirect("adminpanel:dashboard")

        return _wrapped

    return decorator


def paginate_queryset(request, queryset, per_page=20):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page")
    return paginator.get_page(page_number)


@staff_required
def dashboard(request):
    orders = Order.objects.all()
    total_revenue = orders.filter(status__in=["paid", "processing", "shipped", "delivered"]).aggregate(
        Sum("total")
    )["total__sum"] or 0
    pending_orders = orders.filter(status="pending").count()
    processing_orders = orders.filter(status="processing").count()
    delivered = orders.filter(status="delivered").count()

    top_perfumes = (
        OrderItem.objects.filter(perfume__isnull=False)
        .values("perfume__name")
        .annotate(total_qty=Sum("quantity"))
        .order_by("-total_qty")[:5]
    )
    top_pigments = (
        OrderItem.objects.filter(pigment__isnull=False)
        .values("pigment__name")
        .annotate(total_qty=Sum("quantity"))
        .order_by("-total_qty")[:5]
    )

    context = {
        "total_revenue": total_revenue,
        "pending_orders": pending_orders,
        "processing_orders": processing_orders,
        "delivered": delivered,
        "orders_last_week": orders.filter(created_at__gte=timezone.now() - timezone.timedelta(days=7)).count(),
        "top_perfumes": top_perfumes,
        "top_pigments": top_pigments,
    }
    return render(request, "adminpanel/dashboard.html", context)


# ===== Каталог =====

@role_required(*CATALOG_ROLES)
def brand_list(request):
    search = request.GET.get("q")
    items = Brand.objects.all().order_by("name")
    if search:
        items = items.filter(Q(name__icontains=search) | Q(country__icontains=search))
    page_obj = paginate_queryset(request, items)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    base_qs = query_params.urlencode()
    context = {
        "items": page_obj,
        "page_obj": page_obj,
        "search": search,
        "base_qs": base_qs,
    }
    template = "adminpanel/brands/_list.html" if request.headers.get("X-Requested-With") == "XMLHttpRequest" else "adminpanel/brands/list.html"
    return render(request, template, context)


@role_required(*CATALOG_ROLES)
def brand_create(request):
    if request.method == "POST":
        form = BrandForm(request.POST, request.FILES)
        if form.is_valid():
            brand = form.save()
            log_action(request, "brand_create", brand)
            messages.success(request, "Бренд создан")
            return redirect("adminpanel:brand_list")
    else:
        form = BrandForm()
    return render(request, "adminpanel/brands/form.html", {"form": form, "title": "Создать бренд"})


@role_required(*CATALOG_ROLES)
def brand_edit(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == "POST":
        form = BrandForm(request.POST, request.FILES, instance=brand)
        if form.is_valid():
            form.save()
            log_action(request, "brand_edit", brand)
            messages.success(request, "Бренд обновлен")
            return redirect("adminpanel:brand_list")
    else:
        form = BrandForm(instance=brand)
    return render(request, "adminpanel/brands/form.html", {"form": form, "title": "Редактировать бренд"})


@role_required(*CATALOG_ROLES)
def brand_delete(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == "POST":
        brand.delete()
        log_action(request, "brand_delete", brand)
        messages.success(request, "Бренд удален")
        return redirect("adminpanel:brand_list")
    return render(request, "adminpanel/confirm_delete.html", {"object": brand, "back_url": "adminpanel:brand_list"})


@role_required(*CATALOG_ROLES)
def category_list(request):
    search = request.GET.get("q")
    ctype = request.GET.get("type")
    items = Category.objects.all().order_by("category_type", "name")
    if ctype in ["perfume", "pigment"]:
        items = items.filter(category_type=ctype)
    if search:
        items = items.filter(Q(name__icontains=search) | Q(description__icontains=search))
    page_obj = paginate_queryset(request, items)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    base_qs = query_params.urlencode()
    context = {
        "items": page_obj,
        "page_obj": page_obj,
        "search": search,
        "ctype": ctype,
        "base_qs": base_qs,
    }
    template = "adminpanel/categories/_list.html" if request.headers.get("X-Requested-With") == "XMLHttpRequest" else "adminpanel/categories/list.html"
    return render(request, template, context)


@role_required(*CATALOG_ROLES)
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            log_action(request, "category_create", category)
            messages.success(request, "Категория создана")
            return redirect("adminpanel:category_list")
    else:
        form = CategoryForm()
    return render(request, "adminpanel/categories/form.html", {"form": form, "title": "Создать категорию"})


@role_required(*CATALOG_ROLES)
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            log_action(request, "category_edit", category)
            messages.success(request, "Категория обновлена")
            return redirect("adminpanel:category_list")
    else:
        form = CategoryForm(instance=category)
    return render(
        request,
        "adminpanel/categories/form.html",
        {"form": form, "title": "Редактировать категорию"},
    )


@role_required(*CATALOG_ROLES)
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.delete()
        log_action(request, "category_delete", category)
        messages.success(request, "Категория удалена")
        return redirect("adminpanel:category_list")
    return render(
        request,
        "adminpanel/confirm_delete.html",
        {"object": category, "back_url": "adminpanel:category_list"},
    )


@role_required(*CATALOG_ROLES)
def perfume_list(request):
    search = request.GET.get("q")
    in_stock = request.GET.get("in_stock")
    featured = request.GET.get("featured")
    on_sale = request.GET.get("on_sale")

    items = Perfume.objects.select_related("brand", "category").all().order_by("-created_at")
    if search:
        items = items.filter(
            Q(name__icontains=search)
            | Q(brand__name__icontains=search)
            | Q(category__name__icontains=search)
            | Q(description__icontains=search)
        )
    if in_stock == "1":
        items = items.filter(in_stock=True)
    if featured == "1":
        items = items.filter(featured=True)
    if on_sale == "1":
        items = items.filter(Q(discount_percentage__gt=0) | Q(discount_price__isnull=False, discount_price__gt=0))

    page_obj = paginate_queryset(request, items)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    base_qs = query_params.urlencode()
    context = {
        "items": page_obj,
        "page_obj": page_obj,
        "search": search,
        "in_stock": in_stock,
        "featured": featured,
        "on_sale": on_sale,
        "base_qs": base_qs,
    }
    template = "adminpanel/perfumes/_list.html" if request.headers.get("X-Requested-With") == "XMLHttpRequest" else "adminpanel/perfumes/list.html"
    return render(request, template, context)


@role_required(*CATALOG_ROLES)
def perfume_create(request):
    if request.method == "POST":
        form = PerfumeForm(request.POST, request.FILES)
        volume_formset = VolumeOptionFormSet(request.POST, prefix='volume')
        if form.is_valid() and volume_formset.is_valid():
            perfume = form.save()
            volume_formset.instance = perfume
            volume_formset.save()
            _save_images(request, perfume=perfume)
            log_action(request, "perfume_create", perfume)
            messages.success(request, "Товар (парфюм) создан")
            return redirect("adminpanel:perfume_list")
    else:
        form = PerfumeForm()
        volume_formset = VolumeOptionFormSet(prefix='volume')
    image_form = ProductImageForm()
    return render(
        request,
        "adminpanel/perfumes/form.html",
        {"form": form, "image_form": image_form, "volume_formset": volume_formset, "title": "Создать парфюм"},
    )


@role_required(*CATALOG_ROLES)
def perfume_edit(request, pk):
    perfume = get_object_or_404(Perfume, pk=pk)
    if request.method == "POST":
        form = PerfumeForm(request.POST, request.FILES, instance=perfume)
        volume_formset = VolumeOptionFormSet(request.POST, instance=perfume, prefix='volume')
        if form.is_valid() and volume_formset.is_valid():
            perfume = form.save()
            volume_formset.save()
            _save_images(request, perfume=perfume)
            log_action(request, "perfume_edit", perfume)
            messages.success(request, "Товар обновлен")
            return redirect("adminpanel:perfume_list")
    else:
        form = PerfumeForm(instance=perfume)
        volume_formset = VolumeOptionFormSet(instance=perfume, prefix='volume')
    image_form = ProductImageForm()
    return render(
        request,
        "adminpanel/perfumes/form.html",
        {
            "form": form,
            "image_form": image_form,
            "volume_formset": volume_formset,
            "title": "Редактировать парфюм",
            "item": perfume,
            "images": perfume.images.all(),
        },
    )


@role_required(*CATALOG_ROLES)
def perfume_delete(request, pk):
    perfume = get_object_or_404(Perfume, pk=pk)
    if request.method == "POST":
        perfume.delete()
        log_action(request, "perfume_delete", perfume)
        messages.success(request, "Парфюм удален")
        return redirect("adminpanel:perfume_list")
    return render(
        request,
        "adminpanel/confirm_delete.html",
        {"object": perfume, "back_url": "adminpanel:perfume_list"},
    )


@role_required(*CATALOG_ROLES)
def pigment_list(request):
    search = request.GET.get("q")
    in_stock = request.GET.get("in_stock")
    featured = request.GET.get("featured")
    on_sale = request.GET.get("on_sale")

    items = Pigment.objects.select_related("brand", "category").all().order_by("-created_at")
    if search:
        items = items.filter(
            Q(name__icontains=search)
            | Q(brand__name__icontains=search)
            | Q(category__name__icontains=search)
            | Q(description__icontains=search)
        )
    if in_stock == "1":
        items = items.filter(in_stock=True)
    if featured == "1":
        items = items.filter(featured=True)
    if on_sale == "1":
        items = items.filter(Q(discount_percentage__gt=0) | Q(discount_price__isnull=False, discount_price__gt=0))

    page_obj = paginate_queryset(request, items)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    base_qs = query_params.urlencode()
    context = {
        "items": page_obj,
        "page_obj": page_obj,
        "search": search,
        "in_stock": in_stock,
        "featured": featured,
        "on_sale": on_sale,
        "base_qs": base_qs,
    }
    template = "adminpanel/pigments/_list.html" if request.headers.get("X-Requested-With") == "XMLHttpRequest" else "adminpanel/pigments/list.html"
    return render(request, template, context)


@role_required(*CATALOG_ROLES)
def pigment_create(request):
    if request.method == "POST":
        form = PigmentForm(request.POST, request.FILES)
        weight_formset = WeightOptionFormSet(request.POST, prefix='weight')
        if form.is_valid() and weight_formset.is_valid():
            pigment = form.save()
            weight_formset.instance = pigment
            weight_formset.save()
            _save_images(request, pigment=pigment)
            log_action(request, "pigment_create", pigment)
            messages.success(request, "Пигмент создан")
            return redirect("adminpanel:pigment_list")
    else:
        form = PigmentForm()
        weight_formset = WeightOptionFormSet(prefix='weight')
    image_form = ProductImageForm()
    return render(
        request,
        "adminpanel/pigments/form.html",
        {"form": form, "image_form": image_form, "weight_formset": weight_formset, "title": "Создать пигмент"},
    )


@role_required(*CATALOG_ROLES)
def pigment_edit(request, pk):
    pigment = get_object_or_404(Pigment, pk=pk)
    if request.method == "POST":
        form = PigmentForm(request.POST, request.FILES, instance=pigment)
        weight_formset = WeightOptionFormSet(request.POST, instance=pigment, prefix='weight')
        if form.is_valid() and weight_formset.is_valid():
            pigment = form.save()
            weight_formset.save()
            _save_images(request, pigment=pigment)
            log_action(request, "pigment_edit", pigment)
            messages.success(request, "Пигмент обновлен")
            return redirect("adminpanel:pigment_list")
    else:
        form = PigmentForm(instance=pigment)
        weight_formset = WeightOptionFormSet(instance=pigment, prefix='weight')
    image_form = ProductImageForm()
    return render(
        request,
        "adminpanel/pigments/form.html",
        {
            "form": form,
            "image_form": image_form,
            "weight_formset": weight_formset,
            "title": "Редактировать пигмент",
            "item": pigment,
            "images": pigment.images.all(),
        },
    )


@role_required(*CATALOG_ROLES)
def pigment_delete(request, pk):
    pigment = get_object_or_404(Pigment, pk=pk)
    if request.method == "POST":
        pigment.delete()
        log_action(request, "pigment_delete", pigment)
        messages.success(request, "Пигмент удален")
        return redirect("adminpanel:pigment_list")
    return render(
        request,
        "adminpanel/confirm_delete.html",
        {"object": pigment, "back_url": "adminpanel:pigment_list"},
    )


def _save_images(request, perfume=None, pigment=None):
    """Сохранение доп. изображений из формы с базовой валидацией."""
    files = request.FILES.getlist("extra_images")
    if not files:
        return

    MAX_FILES = 10
    if len(files) > MAX_FILES:
        messages.error(request, f"Слишком много файлов за один раз (>{MAX_FILES}). Разделите загрузку.")
        return

    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
    MAX_SIZE_MB = 5
    max_bytes = MAX_SIZE_MB * 1024 * 1024

    # Проверяем дубликаты по имени для текущего товара
    target = perfume or pigment
    existing_names = set()
    if target:
        existing_names = {
            img.image.name.rsplit("/", 1)[-1]
            for img in target.images.all()
            if getattr(img, "image", None)
        }

    rejected = []
    saved = 0
    pillow_unavailable_warned = False
    for f in files:
        filename = f.name
        if filename in existing_names:
            rejected.append(f"{filename}: такое имя уже есть у товара")
            continue

        if f.content_type not in ALLOWED_TYPES:
            rejected.append(f"{f.name}: недопустимый тип ({f.content_type})")
            continue
        if f.size and f.size > max_bytes:
            rejected.append(f"{f.name}: слишком большой (> {MAX_SIZE_MB} МБ)")
            continue

        processed_file = f
        if Image:
            processed_file = _process_image(f)
        else:
            if not pillow_unavailable_warned:
                messages.warning(request, "Pillow не установлен: изображения загружены без сжатия/конвертации.")
                pillow_unavailable_warned = True

        ProductImage.objects.create(perfume=perfume, pigment=pigment, image=processed_file)
        saved += 1

    if rejected:
        messages.error(request, "Некоторые изображения не сохранены: " + "; ".join(rejected))
    if saved:
        logger.info(
            "Extra images saved",
            extra={
                "user": getattr(request, "user", None),
                "saved": saved,
                "rejected": len(rejected),
                "perfume_id": getattr(perfume, "id", None),
                "pigment_id": getattr(pigment, "id", None),
            },
        )


def _process_image(uploaded_file):
    """Ресайз и конвертация в WEBP, если Pillow доступен."""
    if not Image:
        return uploaded_file
    try:
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)
        img = img.convert("RGB")
        max_side = 1600
        img.thumbnail((max_side, max_side))
        buffer = BytesIO()
        img.save(buffer, format="WEBP", quality=85, optimize=True)
        buffer.seek(0)
        name = uploaded_file.name.rsplit(".", 1)[0] + ".webp"
        return ContentFile(buffer.read(), name=name)
    except Exception:
        logger.exception("Image processing failed", extra={"filename": uploaded_file.name})
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return uploaded_file


@role_required(*CATALOG_ROLES)
def product_image_delete(request, pk):
    """Удаление дополнительного изображения товара."""
    image = get_object_or_404(ProductImage, pk=pk)
    redirect_pk = image.perfume_id or image.pigment_id
    redirect_name = "adminpanel:perfume_edit" if image.perfume_id else "adminpanel:pigment_edit"

    if request.method == "POST":
        image.delete()
        messages.success(request, "Изображение удалено")
        logger.info(
            "Product image deleted",
            extra={
                "user": getattr(request, "user", None),
                "image_id": pk,
                "perfume_id": image.perfume_id,
                "pigment_id": image.pigment_id,
            },
        )
        return redirect(redirect_name, pk=redirect_pk)

    # Если GET – возвращаемся к карточке без удаления
    return redirect(redirect_name, pk=redirect_pk)


# ===== Заказы =====

@role_required(*ORDERS_ROLES)
def order_list(request):
    status_filter = request.GET.get("status")
    qs = Order.objects.select_related("user").prefetch_related("items").order_by("-created_at")
    if status_filter:
        qs = qs.filter(status=status_filter)
    page_obj = paginate_queryset(request, qs)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    base_qs = query_params.urlencode()
    context = {
        "orders": page_obj,
        "status_filter": status_filter,
        "page_obj": page_obj,
        "base_qs": base_qs,
    }
    template = "adminpanel/orders/_list.html" if request.headers.get("X-Requested-With") == "XMLHttpRequest" else "adminpanel/orders/list.html"
    return render(request, template, context)


@role_required(*ORDERS_ROLES)
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("user"), pk=pk)
    form = OrderStatusForm(instance=order)
    return render(request, "adminpanel/orders/detail.html", {"order": order, "form": form})


@role_required(*ORDERS_ROLES)
def order_status_update(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == "POST":
        client_updated_at = request.POST.get("updated_at")
        if client_updated_at:
            try:
                posted_dt = timezone.datetime.fromisoformat(client_updated_at)
                if timezone.is_naive(posted_dt):
                    posted_dt = timezone.make_aware(posted_dt, timezone.get_current_timezone())
                if order.updated_at and abs((order.updated_at - posted_dt).total_seconds()) > 1:
                    messages.error(request, "Заказ уже был изменен другим администратором. Обновите страницу.")
                    return redirect("adminpanel:order_detail", pk=pk)
            except ValueError:
                messages.error(request, "Некорректная метка времени. Обновите страницу.")
                return redirect("adminpanel:order_detail", pk=pk)

        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            new_status = form.cleaned_data["status"]
            current_status = order.status
            allowed_transitions = {
                "pending": {"paid", "processing", "cancelled"},
                "paid": {"processing", "shipped", "cancelled"},
                "processing": {"shipped", "cancelled"},
                "shipped": {"delivered"},
                "delivered": set(),
                "cancelled": set(),
            }
            if new_status != current_status and new_status not in allowed_transitions.get(current_status, set()):
                messages.error(
                    request,
                    f"Переход из {order.get_status_display()} в {form.instance.get_status_display()} запрещен",
                )
            else:
                form.save()
                log_action(request, "order_status_update", order, {"status": new_status})
                logger.info("Order %s status changed %s -> %s by %s", order.id, current_status, new_status, request.user)
                messages.success(request, "Статус заказа обновлен")
        else:
            messages.error(request, "Ошибка валидации формы")
    return redirect("adminpanel:order_detail", pk=pk)


# ===== Пользователи =====

@role_required(*USERS_ROLES)
def user_list(request):
    search = request.GET.get("q")
    staff_filter = request.GET.get("staff")
    active_filter = request.GET.get("active")
    date_filter = request.GET.get("date")

    qs = User.objects.select_related("profile", "loyalty_account").prefetch_related("orders").all().order_by("-date_joined")

    # Поиск
    if search:
        qs = qs.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(profile__first_name__icontains=search) |
            Q(profile__last_name__icontains=search)
        )

    # Фильтр по статусу администратора
    if staff_filter == "staff":
        qs = qs.filter(is_staff=True)
    elif staff_filter == "regular":
        qs = qs.filter(is_staff=False)

    # Фильтр по активности
    if active_filter == "active":
        qs = qs.filter(is_active=True)
    elif active_filter == "inactive":
        qs = qs.filter(is_active=False)

    # Фильтр по дате регистрации
    if date_filter == "today":
        qs = qs.filter(date_joined__date=timezone.now().date())
    elif date_filter == "week":
        qs = qs.filter(date_joined__gte=timezone.now() - timezone.timedelta(days=7))
    elif date_filter == "month":
        qs = qs.filter(date_joined__gte=timezone.now() - timezone.timedelta(days=30))

    page_obj = paginate_queryset(request, qs)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    base_qs = query_params.urlencode()

    context = {
        "users": page_obj,
        "search": search,
        "staff_filter": staff_filter,
        "active_filter": active_filter,
        "date_filter": date_filter,
        "page_obj": page_obj,
        "base_qs": base_qs,
    }
    template = "adminpanel/users/_list.html" if request.headers.get("X-Requested-With") == "XMLHttpRequest" else "adminpanel/users/list.html"
    return render(request, template, context)


@role_required(*USERS_ROLES)
def user_detail(request, pk):
    user = get_object_or_404(User, pk=pk)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    settings_obj, _ = UserSettings.objects.get_or_create(user=user)
    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=user)

    # Определяем режим: просмотр или редактирование
    mode = request.GET.get("mode", "view")  # по умолчанию просмотр
    is_edit_mode = mode == "edit"

    if request.method == "POST" and is_edit_mode:
        u_form = UserForm(request.POST, instance=user)
        p_form = UserProfileForm(request.POST, request.FILES, instance=profile)
        s_form = UserSettingsForm(request.POST, instance=settings_obj)

        # Отладка валидации форм
        forms_valid = True
        error_messages = []

        if not u_form.is_valid():
            forms_valid = False
            for field, errors in u_form.errors.items():
                error_messages.extend([f"UserForm - {field}: {error}" for error in errors])

        if not p_form.is_valid():
            forms_valid = False
            for field, errors in p_form.errors.items():
                error_messages.extend([f"UserProfileForm - {field}: {error}" for error in errors])

        if not s_form.is_valid():
            forms_valid = False
            for field, errors in s_form.errors.items():
                error_messages.extend([f"UserSettingsForm - {field}: {error}" for error in errors])

        if forms_valid:
            try:
                u_form.save()
                p_form.save()
                s_form.save()

                # Проверяем, что данные действительно сохранены
                user.refresh_from_db()
                profile.refresh_from_db()

                log_action(request, "user_update", user)
                messages.success(request, "Данные пользователя обновлены")
                # Вместо перенаправления просто перерисовываем страницу
                # return redirect(f"{request.path}?mode=edit")
            except Exception as e:
                logger.exception("Error saving user forms")
                messages.error(request, f"Ошибка при сохранении: {str(e)}")
        else:
            # Выводим детальные ошибки
            if error_messages:
                for error_msg in error_messages[:3]:  # Ограничиваем количество сообщений
                    messages.error(request, error_msg)
            else:
                messages.error(request, "Проверьте поля формы")
    else:
        u_form = UserForm(instance=user)
        p_form = UserProfileForm(instance=profile)
        s_form = UserSettingsForm(instance=settings_obj)

    orders = user.orders.all().order_by("-created_at")[:10]  # Ограничиваем до 10 заказов
    wishlist = getattr(user, "wishlist", None)
    cart = getattr(user, "cart", None)
    loyalty_tx = LoyaltyTransaction.objects.filter(user=user).order_by("-created_at")[:10]  # Ограничиваем до 10 транзакций

    return render(
        request,
        "adminpanel/users/detail.html",
        {
            "obj": user,
            "u_form": u_form,
            "p_form": p_form,
            "s_form": s_form,
            "orders": orders,
            "wishlist": wishlist,
            "cart": cart,
            "loyalty": loyalty,
            "loyalty_tx": loyalty_tx,
            "adjust_form": LoyaltyAdjustForm(),
            "is_edit_mode": is_edit_mode,
            "mode": mode,
        },
    )


@role_required(*USERS_ROLES)
def user_loyalty_update(request, pk):
    user = get_object_or_404(User, pk=pk)
    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=user)
    if request.method == "POST":
        form = LoyaltyAdjustForm(request.POST)
        if form.is_valid():
            points = form.cleaned_data["points"]
            description = form.cleaned_data.get("description") or "Корректировка администратором"
            new_balance = loyalty.balance + points
            if new_balance < 0:
                messages.error(request, "Нельзя увести баланс в минус.")
                return redirect("adminpanel:user_detail", pk=pk)

            loyalty.balance = new_balance
            loyalty.save()
            LoyaltyTransaction.objects.create(
                user=user,
                order=None,
                transaction_type="adjust" if points >= 0 else "redeem",
                points=points,
                description=description,
                balance_after=loyalty.balance,
            )
            log_action(request, "loyalty_adjust", user, {"points": points})
            messages.success(request, "Баланс обновлен")
        else:
            messages.error(request, "Ошибка валидации формы")
    return redirect("adminpanel:user_detail", pk=pk)


# ===== Акции и скидки =====

@role_required(*CATALOG_ROLES)
def discount_list(request):
    """Список всех товаров с активными акциями"""
    # Получаем товары с активными скидками
    perfumes_on_sale = Perfume.objects.filter(
        Q(discount_percentage__gt=0) |
        Q(discount_price__isnull=False, discount_price__gt=0)
    ).filter(
        Q(discount_start_date__isnull=True) |
        Q(discount_start_date__lte=timezone.now())
    ).filter(
        Q(discount_end_date__isnull=True) |
        Q(discount_end_date__gte=timezone.now())
    )

    pigments_on_sale = Pigment.objects.filter(
        Q(discount_percentage__gt=0) |
        Q(discount_price__isnull=False, discount_price__gt=0)
    ).filter(
        Q(discount_start_date__isnull=True) |
        Q(discount_start_date__lte=timezone.now())
    ).filter(
        Q(discount_end_date__isnull=True) |
        Q(discount_end_date__gte=timezone.now())
    )

    # Получаем активные промо-акции
    active_promotions = Promotion.objects.filter(active=True).select_related('brand', 'category').order_by('priority', '-created_at')

    context = {
        "perfumes_on_sale": perfumes_on_sale,
        "pigments_on_sale": pigments_on_sale,
        "active_promotions": active_promotions,
        "total_discounts": perfumes_on_sale.count() + pigments_on_sale.count(),
        "total_promotions": active_promotions.count(),
    }
    return render(request, "adminpanel/discounts/list.html", context)


@role_required(*CATALOG_ROLES)
def discount_create(request):
    """Создание акции для товара"""
    product_type = request.GET.get('type', 'perfume')  # perfume или pigment
    product_id = request.GET.get('id')

    if not product_id:
        messages.error(request, "Не указан товар для акции")
        return redirect("adminpanel:discount_list")

    try:
        if product_type == 'perfume':
            product = Perfume.objects.get(pk=product_id)
            form_class = PerfumeForm
            redirect_url = "adminpanel:perfume_list"
        else:
            product = Pigment.objects.get(pk=product_id)
            form_class = PigmentForm
            redirect_url = "adminpanel:pigment_list"

        if request.method == "POST":
            form = form_class(request.POST, request.FILES, instance=product)
            if form.is_valid():
                form.save()
                log_action(request, "discount_create", product, {"product_type": product_type})
                messages.success(request, "Акция создана/обновлена")
                return redirect(redirect_url)
        else:
            form = form_class(instance=product)

        context = {
            "form": form,
            "product": product,
            "product_type": product_type,
            "title": f"Акция для {product.name}"
        }
        return render(request, "adminpanel/discounts/form.html", context)

    except (Perfume.DoesNotExist, Pigment.DoesNotExist):
        messages.error(request, "Товар не найден")
        return redirect("adminpanel:discount_list")


@role_required(*CATALOG_ROLES)
def discount_manage(request):
    """Массовое управление акциями: фильтрация, выбор товаров, применение/сброс"""

    # Обработка редактирования существующей промо-акции
    promo_id = request.GET.get("promo")
    editing_promo = None
    if promo_id:
        try:
            editing_promo = Promotion.objects.get(id=promo_id)
        except Promotion.DoesNotExist:
            messages.error(request, "Акция не найдена")
            return redirect("adminpanel:discount_list")

    # Фильтры
    product_type = request.GET.get("type", "all")
    brand_id = request.GET.get("brand")
    category_id = request.GET.get("category")
    search = request.GET.get("search")

    perfumes = Perfume.objects.select_related("brand", "category").all()
    pigments = Pigment.objects.select_related("brand", "category").all()

    if brand_id:
        perfumes = perfumes.filter(brand_id=brand_id)
        pigments = pigments.filter(brand_id=brand_id)
    if category_id:
        perfumes = perfumes.filter(category_id=category_id)
        pigments = pigments.filter(category_id=category_id)
    if search:
        perfumes = perfumes.filter(
            Q(name__icontains=search) | Q(brand__name__icontains=search) | Q(category__name__icontains=search)
        )
        pigments = pigments.filter(
            Q(name__icontains=search) | Q(brand__name__icontains=search) | Q(category__name__icontains=search)
        )
    if product_type == "perfume":
        pigments = pigments.none()
    elif product_type == "pigment":
        perfumes = perfumes.none()

    # Ограничиваем объем выборки, чтобы не рендерить слишком много карточек
    MAX_ITEMS = 200
    perfumes = perfumes.order_by("-created_at")[:MAX_ITEMS]
    pigments = pigments.order_by("-created_at")[:MAX_ITEMS]

    # Обработка деактивации промо-акций
    if request.method == "POST" and request.POST.get("action") == "deactivate_promo":
        promo_id = request.POST.get("promo_id")
        try:
            promo = Promotion.objects.get(id=promo_id)
            promo.clear_discounts()  # Сбрасываем скидки у товаров
            promo.active = False
            promo.save()
            messages.success(request, f"Акция '{promo.title or promo.id}' деактивирована")
            log_action(request, "promo_deactivate", promo)
        except Promotion.DoesNotExist:
            messages.error(request, "Акция не найдена")
        return redirect("adminpanel:discount_list")

    # Если создаем/обновляем промо, подменим action до валидации формы
    if request.method == "POST" and (request.POST.get("action") == "create_promo" or request.POST.get("action") == "update_promo"):
        post = request.POST.copy()
        post["action"] = "apply"
        form = DiscountBulkForm(post)
    else:
        # Предварительное заполнение формы данными промо-акции при редактировании
        initial_data = {}
        if editing_promo:
            initial_data = {
                "discount_percentage": editing_promo.discount_percentage,
                "discount_price": editing_promo.discount_price,
                "discount_start_date": editing_promo.start_at,
                "discount_end_date": editing_promo.end_at,
            }
        form = DiscountBulkForm(request.POST or None, initial=initial_data)

    # Создание/обновление промо из выбранных товаров
    if request.method == "POST" and (request.POST.get("action") == "create_promo" or request.POST.get("action") == "update_promo"):
        items = request.POST.getlist("items")
        if not items:
            messages.error(request, "Выберите товары для промо")
            return redirect("adminpanel:discount_manage")

        if not form.is_valid():
            error_text = "; ".join([err for errs in form.errors.values() for err in errs])
            messages.error(request, error_text or "Исправьте ошибки формы")
            return redirect("adminpanel:discount_manage")

        discount_percentage = form.cleaned_data.get("discount_percentage") or 0
        discount_price = form.cleaned_data.get("discount_price")
        start_at = form.cleaned_data.get("discount_start_date")
        end_at = form.cleaned_data.get("discount_end_date")

        title = request.POST.get("promo_title") or ""
        slot = request.POST.get("promo_slot") or "homepage_deals_1"
        priority = int(request.POST.get("promo_priority") or 0)

        # Если редактируем существующую промо-акцию
        if editing_promo:
            # Сначала сбрасываем старые скидки
            editing_promo.clear_discounts()

            # Обновляем данные промо-акции
            editing_promo.title = title
            editing_promo.slot = slot
            editing_promo.discount_percentage = discount_percentage
            editing_promo.discount_price = discount_price
            editing_promo.start_at = start_at or None
            editing_promo.end_at = end_at or None
            editing_promo.priority = priority
            editing_promo.active = True  # Активируем при обновлении
            editing_promo.save()

            promo = editing_promo
            log_action(request, "promo_update", promo)
            messages.success(request, f"Акция обновлена: {promo.title or promo.id}")
        else:
            # Создаем новую промо-акцию
            promo = Promotion.objects.create(
                title=title,
                promo_type="manual",
                slot=slot,
                discount_percentage=discount_percentage,
                discount_price=discount_price,
                start_at=start_at or None,
                end_at=end_at or None,
                priority=priority,
                apply_prices=True,
                active=False,
            )
            log_action(request, "promo_create", promo)
            messages.success(request, f"Акция создана: {promo.title or promo.id}")

        perf_ids = []
        pigm_ids = []
        for raw in items:
            try:
                ptype, pid = raw.split(":")
                pid = int(pid)
            except ValueError:
                continue
            if ptype == "perfume":
                perf_ids.append(pid)
            elif ptype == "pigment":
                pigm_ids.append(pid)

        # Очищаем старые связи и добавляем новые
        promo.perfumes.clear()
        promo.pigments.clear()
        if perf_ids:
            promo.perfumes.add(*Perfume.objects.filter(id__in=perf_ids))
        if pigm_ids:
            promo.pigments.add(*Pigment.objects.filter(id__in=pigm_ids))

        promo.apply_discounts()
        return redirect("adminpanel:discount_manage")

    if request.method == "POST":
        items = request.POST.getlist("items")
        if not items:
            messages.error(request, "Выберите товары для применения акции")
            return redirect("adminpanel:discount_manage")

        # Дополнительная защита от слишком больших выборок — предотвращаем
        # случайное применение скидок к сотням позиций разом.
        MAX_SELECTED = 100
        if len(items) > MAX_SELECTED:
            messages.error(request, f"Выбрано слишком много товаров ({len(items)}). Лимит: {MAX_SELECTED}. Сузьте выборку.")
            return redirect("adminpanel:discount_manage")

        if not form.is_valid():
            error_text = "; ".join([err for errs in form.errors.values() for err in errs])
            messages.error(request, error_text or "Исправьте ошибки формы")
            return redirect("adminpanel:discount_manage")

        action = form.cleaned_data["action"]
        discount_percentage = form.cleaned_data.get("discount_percentage") or 0
        discount_price = form.cleaned_data.get("discount_price")
        start_date = form.cleaned_data.get("discount_start_date")
        end_date = form.cleaned_data.get("discount_end_date")

        updated = 0
        skipped = []
        with transaction.atomic():
            for raw in items:
                try:
                    ptype, pid = raw.split(":")
                    pid = int(pid)
                except ValueError:
                    continue

                product = None
                if ptype == "perfume":
                    product = Perfume.objects.select_for_update().filter(pk=pid).first()
                elif ptype == "pigment":
                    product = Pigment.objects.select_for_update().filter(pk=pid).first()
                if not product:
                    continue

                if action == "clear":
                    product.discount_percentage = 0
                    product.discount_price = None
                    product.discount_start_date = None
                    product.discount_end_date = None
                else:
                    # Дополнительная защита от некорректной цены
                    if discount_price is not None and product.price is not None and discount_price >= product.price:
                        skipped.append(product.name)
                        continue
                    product.discount_percentage = discount_percentage
                    product.discount_price = discount_price
                    product.discount_start_date = start_date
                    product.discount_end_date = end_date
                product.save()
                updated += 1

        if updated:
            if action == "clear":
                messages.success(request, f"Скидки сброшены для {updated} товар(ов)")
            else:
                msg = f"Скидки применены к {updated} товар(ов)"
                if skipped:
                    msg += f". Пропущено (цена выше исходной): {', '.join(skipped[:5])}" + ("…" if len(skipped) > 5 else "")
                messages.success(request, msg)
            logger.info(
                "Bulk discount action applied",
                extra={
                    "user": getattr(request, "user", None),
                    "action": action,
                    "updated": updated,
                    "skipped": skipped[:10],
                    "filters": {
                        "product_type": product_type,
                        "brand_id": brand_id,
                        "category_id": category_id,
                        "search": search,
                    },
                },
            )
        else:
            messages.info(request, "Ничего не изменено")
        return redirect("adminpanel:discount_manage")

    # Проверка на AJAX запрос
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Возвращаем только HTML блок с товарами для AJAX
        context = {
            "perfumes": perfumes,
            "pigments": pigments,
        }
        return render(request, "adminpanel/discounts/_products.html", context)

    # Получаем выбранные товары для промо-акции если редактируем
    selected_promo_items = []
    promo_data = {}
    if editing_promo:
        selected_promo_items = [
            f"perfume:{p.id}" for p in editing_promo.perfumes.all()
        ] + [
            f"pigment:{p.id}" for p in editing_promo.pigments.all()
        ]
        promo_data = {
            "title": editing_promo.title or "",
            "slot": editing_promo.slot,
            "priority": editing_promo.priority,
            "discount_percentage": editing_promo.discount_percentage,
            "discount_price": str(editing_promo.discount_price) if editing_promo.discount_price else "",
            "start_at": editing_promo.start_at.isoformat() if editing_promo.start_at else "",
            "end_at": editing_promo.end_at.isoformat() if editing_promo.end_at else "",
        }

    context = {
        "perfumes": perfumes,
        "pigments": pigments,
        "filters": {
            "product_type": product_type,
            "brand": brand_id,
            "category": category_id,
            "search": search,
        },
        "brands": Brand.objects.all(),
        "categories": Category.objects.all(),
        "form": form,
        "editing_promo": editing_promo,
        "selected_promo_items": selected_promo_items,
        "promo_data": promo_data,
    }
    return render(request, "adminpanel/discounts/manage.html", context)


@role_required(*CATALOG_ROLES)
def trending_manage(request):
    """Управление блоком 'В тренде сейчас'."""

    # Фильтры и выборка товаров (переиспользуем то же, что в скидках)
    product_type = request.GET.get("type", "all")
    brand_id = request.GET.get("brand")
    category_id = request.GET.get("category")
    discount_filter = request.GET.get("discount", "all")
    search = request.GET.get("search")

    perfumes = Perfume.objects.select_related("brand", "category").all()
    pigments = Pigment.objects.select_related("brand", "category").all()

    if brand_id:
        perfumes = perfumes.filter(brand_id=brand_id)
        pigments = pigments.filter(brand_id=brand_id)
    if category_id:
        perfumes = perfumes.filter(category_id=category_id)
        pigments = pigments.filter(category_id=category_id)
    if search:
        perfumes = perfumes.filter(
            Q(name__icontains=search) | Q(brand__name__icontains=search) | Q(category__name__icontains=search)
        )
        pigments = pigments.filter(
            Q(name__icontains=search) | Q(brand__name__icontains=search) | Q(category__name__icontains=search)
        )

    # Фильтр по скидкам
    if discount_filter == "with_discount":
        perfumes = perfumes.filter(
            Q(discount_percentage__gt=0) | Q(discount_price__isnull=False, discount_price__gt=0)
        ).filter(
            Q(discount_start_date__isnull=True) | Q(discount_start_date__lte=timezone.now())
        ).filter(
            Q(discount_end_date__isnull=True) | Q(discount_end_date__gte=timezone.now())
        )
        pigments = pigments.filter(
            Q(discount_percentage__gt=0) | Q(discount_price__isnull=False, discount_price__gt=0)
        ).filter(
            Q(discount_start_date__isnull=True) | Q(discount_start_date__lte=timezone.now())
        ).filter(
            Q(discount_end_date__isnull=True) | Q(discount_end_date__gte=timezone.now())
        )
    elif discount_filter == "without_discount":
        perfumes = perfumes.filter(
            Q(discount_percentage=0) & (Q(discount_price__isnull=True) | Q(discount_price=0))
        )
        pigments = pigments.filter(
            Q(discount_percentage=0) & (Q(discount_price__isnull=True) | Q(discount_price=0))
        )

    if product_type == "perfume":
        pigments = pigments.none()
    elif product_type == "pigment":
        perfumes = perfumes.none()

    MAX_ITEMS = 200
    perfumes = perfumes.order_by("-created_at")[:MAX_ITEMS]
    pigments = pigments.order_by("-created_at")[:MAX_ITEMS]

    if request.method == "POST":
        items = request.POST.getlist("items")

        # Создаем множество выбранных товаров
        selected_product_keys = set()
        selected_items = []
        for raw in items:
            try:
                ptype, pid = raw.split(":")
                pid = int(pid)
                product_key = f"{ptype}:{pid}"
                selected_product_keys.add(product_key)
                selected_items.append((ptype, pid))
            except ValueError:
                continue

        # Получаем текущие трендовые товары
        current_trending = list(TrendingProduct.objects.all())
        current_product_keys = set()

        # Создаем множество текущих товаров
        for trending_item in current_trending:
            if trending_item.product_type == 'perfume' and trending_item.perfume_id:
                current_product_keys.add(f"perfume:{trending_item.perfume_id}")
            elif trending_item.product_type == 'pigment' and trending_item.pigment_id:
                current_product_keys.add(f"pigment:{trending_item.pigment_id}")

        # Определяем товары для удаления (были выбраны, но теперь не выбраны)
        items_to_remove = current_product_keys - selected_product_keys

        # Определяем товары для добавления (новые выбранные)
        items_to_add = selected_product_keys - current_product_keys

        # Проверяем ограничение на 6 товаров
        final_count = len(selected_product_keys)
        if final_count > 6:
            messages.error(request, f"Можно выбрать максимум 6 товаров. Выбрано: {final_count}")
            return redirect("adminpanel:trending_manage")

        with transaction.atomic():
            # Удаляем товары, которые больше не выбраны
            for product_key in items_to_remove:
                ptype, pid = product_key.split(":")
                pid = int(pid)
                if ptype == "perfume":
                    TrendingProduct.objects.filter(product_type='perfume', perfume_id=pid).delete()
                elif ptype == "pigment":
                    TrendingProduct.objects.filter(product_type='pigment', pigment_id=pid).delete()

            # Добавляем новые товары
            for product_key in items_to_add:
                ptype, pid = product_key.split(":")
                pid = int(pid)
                if ptype == "perfume":
                    prod = Perfume.objects.filter(pk=pid).first()
                    if prod:
                        TrendingProduct.objects.create(
                            product_type='perfume',
                            perfume=prod,
                            position=0  # Временная позиция, пересчитаем ниже
                        )
                elif ptype == "pigment":
                    prod = Pigment.objects.filter(pk=pid).first()
                    if prod:
                        TrendingProduct.objects.create(
                            product_type='pigment',
                            pigment=prod,
                            position=0  # Временная позиция, пересчитаем ниже
                        )

            # Пересчитываем позиции для всех оставшихся товаров в соответствии с порядком выбора
            position = 0
            for ptype, pid in selected_items:
                if ptype == "perfume":
                    TrendingProduct.objects.filter(product_type='perfume', perfume_id=pid).update(position=position)
                elif ptype == "pigment":
                    TrendingProduct.objects.filter(product_type='pigment', pigment_id=pid).update(position=position)
                position += 1

        removed_count = len(items_to_remove)
        added_count = len(items_to_add)

        if removed_count > 0 or added_count > 0:
            messages.success(request, f"Обновлено: добавлено {added_count}, удалено {removed_count} товар(ов). Всего {final_count}/6 в блоке 'В тренде сейчас'")
        else:
            messages.info(request, "Выбор товаров не изменился")

        return redirect("adminpanel:trending_manage")

    # AJAX partial
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        context = {
            "perfumes": perfumes,
            "pigments": pigments,
            "selected_ids": [
                f"perfume:{pid}" if ptype == 'perfume' else f"pigment:{gid}"
                for ptype, pid, gid, _pos in TrendingProduct.objects.order_by('position').values_list('product_type', 'perfume_id', 'pigment_id', 'position')
            ],
        }
        return render(request, "adminpanel/trending/_products.html", context)

    context = {
        "perfumes": perfumes,
        "pigments": pigments,
        "brands": Brand.objects.all(),
        "categories": Category.objects.all(),
        "filters": {
            "product_type": product_type,
            "brand": brand_id,
            "category": category_id,
            "discount": discount_filter,
            "search": search,
        },
        "selected_ids": [
            f"perfume:{pid}" if ptype == 'perfume' else f"pigment:{gid}"
            for ptype, pid, gid, _pos in TrendingProduct.objects.order_by('position').values_list('product_type', 'perfume_id', 'pigment_id', 'position')
        ],
        "selected": [
            (ptype, pid, gid)
            for ptype, pid, gid, _pos in TrendingProduct.objects.order_by('position').values_list('product_type', 'perfume_id', 'pigment_id', 'position')
        ],
    }
    return render(request, "adminpanel/trending/manage.html", context)

@role_required(*CATALOG_ROLES)
def discount_remove(request, product_type, pk):
    """Удаление акции (сброс скидки)"""
    try:
        if product_type == 'perfume':
            product = Perfume.objects.get(pk=pk)
            redirect_url = "adminpanel:perfume_list"
        else:
            product = Pigment.objects.get(pk=pk)
            redirect_url = "adminpanel:pigment_list"

        # Сбрасываем поля скидки
        product.discount_percentage = 0
        product.discount_price = None
        product.discount_start_date = None
        product.discount_end_date = None
        product.save()

        log_action(request, "discount_remove", product, {"product_type": product_type})
        messages.success(request, "Акция удалена")
        logger.info(
            "Discount removed",
            extra={
                "user": getattr(request, "user", None),
                "product_type": product_type,
                "product_id": pk,
            },
        )
        return redirect(redirect_url)

    except (Perfume.DoesNotExist, Pigment.DoesNotExist):
        messages.error(request, "Товар не найден")
        return redirect("adminpanel:discount_list")

