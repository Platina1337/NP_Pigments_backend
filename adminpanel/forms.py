from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from django.utils import timezone
from store.models import (
    Brand,
    Category,
    Perfume,
    Pigment,
    ProductImage,
    Promotion,
    Order,
    LoyaltyAccount,
    LoyaltyTransaction,
    UserProfile,
    UserSettings,
    VolumeOption,
    WeightOption,
)


# Inline formsets for volume/weight options
VolumeOptionFormSet = inlineformset_factory(
    Perfume,
    VolumeOption,
    fields=['volume_ml', 'price', 'discount_percentage', 'stock_quantity', 'in_stock', 'is_default'],
    extra=1,
    can_delete=True,
)

WeightOptionFormSet = inlineformset_factory(
    Pigment,
    WeightOption,
    fields=['weight_gr', 'price', 'discount_percentage', 'stock_quantity', 'in_stock', 'is_default'],
    extra=1,
    can_delete=True,
)


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name", "description", "country", "logo"]


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "category_type", "icon"]


class PerfumeForm(forms.ModelForm):
    class Meta:
        model = Perfume
        fields = [
            "name",
            "brand",
            "category",
            "slug",
            "sku",
            "description",
            "gender",
            "price",
            "discount_percentage",
            "discount_price",
            "discount_start_date",
            "discount_end_date",
            "volume_ml",
            "concentration",
            "top_notes",
            "heart_notes",
            "base_notes",
            "image",
            "in_stock",
            "stock_quantity",
            "featured",
        ]

    def clean(self):
        cleaned = super().clean()
        price = cleaned.get("price")
        discount_price = cleaned.get("discount_price")

        if price is not None and discount_price is not None and discount_price > 0:
            if discount_price >= price:
                self.add_error("discount_price", "Цена со скидкой должна быть меньше обычной цены.")

        return cleaned


class PigmentForm(forms.ModelForm):
    class Meta:
        model = Pigment
        fields = [
            "name",
            "brand",
            "category",
            "slug",
            "sku",
            "description",
            "color_code",
            "color_type",
            "application_type",
            "price",
            "discount_percentage",
            "discount_price",
            "discount_start_date",
            "discount_end_date",
            "weight_gr",
            "image",
            "in_stock",
            "stock_quantity",
            "featured",
        ]

    def clean(self):
        cleaned = super().clean()
        price = cleaned.get("price")
        discount_price = cleaned.get("discount_price")

        if price is not None and discount_price is not None and discount_price > 0:
            if discount_price >= price:
                self.add_error("discount_price", "Цена со скидкой должна быть меньше обычной цены.")

        return cleaned


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ["perfume", "pigment", "image", "alt_text"]


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["status", "admin_notes", "tracking_number"]


class LoyaltyAdjustForm(forms.Form):
    points = forms.IntegerField(label="Баллы (+/-)")
    description = forms.CharField(label="Комментарий", required=False, widget=forms.Textarea)


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["first_name", "last_name", "phone", "avatar", "date_of_birth"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # В админ-панели first_name и last_name обрабатываются в UserForm,
        # поэтому убираем их из UserProfileForm чтобы избежать конфликтов
        if 'first_name' in self.fields:
            del self.fields['first_name']
        if 'last_name' in self.fields:
            del self.fields['last_name']


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = ["theme", "notifications_enabled", "email_newsletter"]


class UserForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=False, label="Имя")
    last_name = forms.CharField(max_length=30, required=False, label="Фамилия")

    class Meta:
        model = User
        fields = ["username", "email", "is_active", "is_staff"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            try:
                profile = self.instance.profile
                self.fields['first_name'].initial = profile.first_name or ''
                self.fields['last_name'].initial = profile.last_name or ''
            except UserProfile.DoesNotExist:
                self.fields['first_name'].initial = ''
                self.fields['last_name'].initial = ''

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Сохраняем first_name и last_name в профиль
            profile, created = UserProfile.objects.get_or_create(user=user)

            # Получаем данные из формы
            first_name = self.cleaned_data.get('first_name', '').strip()
            last_name = self.cleaned_data.get('last_name', '').strip()

            profile.first_name = first_name
            profile.last_name = last_name
            profile.save()
        return user


class DiscountBulkForm(forms.Form):
    """Форма для массового применения/сброса акций"""

    ACTION_CHOICES = [
        ("apply", "Применить скидку"),
        ("clear", "Сбросить скидку"),
    ]

    action = forms.ChoiceField(choices=ACTION_CHOICES, label="Действие", initial="apply")
    discount_percentage = forms.IntegerField(
        label="Скидка (%)", required=False, min_value=0, max_value=100, help_text="0-100"
    )
    discount_price = forms.DecimalField(
        label="Фиксированная цена", required=False, min_value=0, decimal_places=2, max_digits=10
    )
    discount_start_date = forms.DateTimeField(
        label="Начало акции", required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    discount_end_date = forms.DateTimeField(
        label="Конец акции", required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action")
        percent = cleaned.get("discount_percentage")
        price = cleaned.get("discount_price")
        start = cleaned.get("discount_start_date")
        end = cleaned.get("discount_end_date")

        if action == "apply":
            if (percent is None or percent == 0) and (price in (None, 0)):
                raise forms.ValidationError("Укажите процент или цену скидки.")

            if percent is not None and (percent < 0 or percent > 100):
                raise forms.ValidationError("Скидка должна быть в диапазоне 0-100%.")

            if price is not None and price <= 0:
                raise forms.ValidationError("Фиксированная цена должна быть больше нуля.")

            if start and end:
                # Приводим к aware датам если нужно
                if timezone.is_naive(start):
                    start = timezone.make_aware(start, timezone.get_current_timezone())
                if timezone.is_naive(end):
                    end = timezone.make_aware(end, timezone.get_current_timezone())
                if end < start:
                    raise forms.ValidationError("Дата окончания не может быть раньше даты начала.")
                cleaned["discount_start_date"] = start
                cleaned["discount_end_date"] = end

        return cleaned


class PromotionForm(forms.ModelForm):
    """Форма для создания/редактирования промо-акций"""

    class Meta:
        model = Promotion
        fields = [
            "title",
            "promo_type",
            "slot",
            "priority",
            "active",
            "start_at",
            "end_at",
            "discount_percentage",
            "discount_price",
            "brand",
            "category",
        ]
        widgets = {
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Фильтруем бренды и категории по типу товаров
        self.fields['brand'].queryset = Brand.objects.all().order_by('name')
        self.fields['category'].queryset = Category.objects.all().order_by('category_type', 'name')

    def clean(self):
        cleaned = super().clean()
        promo_type = cleaned.get("promo_type")
        brand = cleaned.get("brand")
        category = cleaned.get("category")

        if promo_type == "brand" and not brand:
            raise forms.ValidationError("Для акции по бренду необходимо выбрать бренд.")
        if promo_type == "category" and not category:
            raise forms.ValidationError("Для акции по категории необходимо выбрать категорию.")

        start_at = cleaned.get("start_at")
        end_at = cleaned.get("end_at")
        if start_at and end_at and end_at < start_at:
            raise forms.ValidationError("Дата окончания не может быть раньше даты начала.")

        return cleaned

