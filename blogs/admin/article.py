# blogs/admin/article.py

from django import forms
from django.contrib import admin
from django.db import models
from django.db.models import Count
from django.forms.widgets import Textarea
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from blogs.models import Article, ArticleSection
from lib.erp_base.admin.base import BaseAdmin


class ArticleSectionForm(forms.ModelForm):
    """
    Enforce mutual exclusivity of content/image based on section_type.
    Model.clean() already validates required presence; here we add UX-level errors.
    """

    class Meta:
        model = ArticleSection
        fields = ["section_type", "content", "image", "image_alt", "order"]

    def clean(self):
        cleaned = super().clean()
        section_type = cleaned.get("section_type")
        content = cleaned.get("content")
        image = cleaned.get("image")

        if section_type == "image":
            if not image:
                self.add_error("image", _("تصویر برای بخش تصویری الزامی است"))
            if content:
                self.add_error(
                    "content", _("بخش تصویری نباید محتوای متنی داشته باشد")
                )
        else:
            if not content:
                self.add_error(
                    "content", _("محتوا برای این نوع بخش الزامی است")
                )
            if image:
                self.add_error("image", _("بخش متنی نباید تصویر داشته باشد"))
        return cleaned


class ArticleSectionInline(admin.TabularInline):
    """
    Inline for managing sections. Keeps ordering stable and provides image preview.
    """
    model = ArticleSection
    form = ArticleSectionForm
    extra = 0
    fields = ("section_type", "content", "image", "image_alt", "order",
              "image_preview")
    readonly_fields = ("image_preview",)
    ordering = ("order",)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        # Compact textarea + small order field for better UX in inlines
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "content":
            field.widget.attrs.update({"rows": 3})
        elif db_field.name == "order":
            field.widget.attrs.update({"style": "width: 60px;"})
            field.help_text = _(
                "ترتیب نمایش (اگر 0 باشد، به‌صورت خودکار تعیین می‌شود)"
            )
        return field

    def get_queryset(self, request):
        """Ensure sections are ordered by 'order'."""
        return super().get_queryset(request).order_by("order")

    class Media:
        js = ("admin/js/jquery.init.js", "admin/js/inlines.js",
              "admin/js/article_section_ordering.js")
        css = {"all": ("admin/css/changelists.css",)}

    @admin.display(description=_("پیش‌نمایش تصویر"))
    def image_preview(self, obj):
        if getattr(obj, "image", None):
            return format_html(
                '<img src="{}" style="max-width:80px; max-height:80px; border-radius:4px;" />',
                obj.image.url,
            )
        return _("بدون تصویر")


@admin.register(Article)
class ArticleAdmin(BaseAdmin):
    """
    Optimized Article admin:
    - Annotates section_count (avoids N+1 on .sections.count()).
    - Safe bulk actions for publish/draft/feature/unfeature/archive.
    - Autocomplete for tags to handle large vocabularies (lighter than filter_horizontal).
    """
    list_display = [
        "title",
        "author",
        "status",
        "is_featured",
        "view_count",
        "section_count",
        "published_at",
        "jalali_creation_date_time",
    ]
    list_filter = ["status", "is_featured", "author", "tags", "published_at",
                   "created_at"]
    search_fields = ["title", "excerpt", "author__username",
                     "author__first_name", "author__last_name"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["view_count", "jalali_creation_date_time",
                       "jalali_update_date_time", "featured_image_preview"]
    # Prefer autocomplete for scalability. (Do not combine with filter_horizontal for same field)
    autocomplete_fields = ["tags"]
    date_hierarchy = "published_at"
    list_select_related = ("author",)
    actions = ["make_published", "make_draft", "make_featured",
               "remove_featured", "make_archived"]
    inlines = [ArticleSectionInline]
    list_per_page = 50

    formfield_overrides = {
        models.TextField: {
            "widget": Textarea(
                attrs={
                    "rows": 15, "cols": 80,
                    "style": "font-family: monospace; font-size: 14px;"
                }
            )
        },
    }

    fieldsets = (
        (_("محتوا اصلی"), {"fields": ("title", "slug", "excerpt")}),
        (_("تصویر شاخص"), {
            "fields": ("featured_image", "featured_image_preview"),
            "classes": ("collapse",)
        }),
        (_("تنظیمات انتشار"),
         {"fields": ("status", "published_at", "is_featured", "tags")}),
        (_("آمار"), {"fields": ("view_count",), "classes": ("collapse",)}),
        (_("زمان‌بندی"), {
            "fields": ("jalali_creation_date_time", "jalali_update_date_time"),
            "classes": ("collapse",)
        }),
    )

    def get_queryset(self, request):
        """
        Use annotations to avoid per-row counts; prefetch tags & sections for admin display.
        """
        qs = (
            super()
            .get_queryset(request)
            .select_related("author")
            .prefetch_related("tags", "sections")
            .annotate(section_count_anno=Count("sections", distinct=True))
        )
        return qs

    @admin.display(description=_("تعداد بخش‌ها"))
    def section_count(self, obj):
        # Use annotated value if present; fallback to cached prefetch (len()).
        return getattr(obj, "section_count_anno", None) or len(
            getattr(obj, "sections").all()
        )

    @admin.display(description=_("پیش‌نمایش تصویر شاخص"))
    def featured_image_preview(self, obj):
        if getattr(obj, "featured_image", None):
            return format_html(
                '<img src="{}" style="max-width:200px; max-height:200px; border-radius:8px; '
                'box-shadow:0 2px 8px rgba(0,0,0,0.1);" />',
                obj.featured_image.url,
            )
        return _("بدون تصویر شاخص")

    # --- Bulk actions (safe & idempotent) ---

    @admin.action(description=_("انتشار مقالات انتخاب شده"))
    def make_published(self, request, queryset):
        """
        Publish selected articles. Only set published_at if it's null to preserve original schedule.
        """
        now = timezone.localtime(timezone.now())
        updated = queryset.filter(published_at__isnull=True).update(
            status="published", published_at=now
        )
        # For those already with a timestamp, just ensure status=published
        updated2 = queryset.filter(published_at__isnull=False).update(
            status="published"
        )
        self.message_user(request, f"{updated + updated2} مقاله منتشر شد.")

    @admin.action(description=_("تبدیل به پیش‌نویس"))
    def make_draft(self, request, queryset):
        """
        Move back to draft. Clear published_at to align with the 'published' manager semantics.
        """
        updated = queryset.update(status="draft", published_at=None)
        self.message_user(request, f"{updated} مقاله به پیش‌نویس تبدیل شد.")

    @admin.action(description=_("تبدیل به مقاله ویژه"))
    def make_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f"{updated} مقاله به عنوان ویژه انتخاب شد.")

    @admin.action(description=_("حذف از مقالات ویژه"))
    def remove_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f"{updated} مقاله از مقالات ویژه حذف شد.")

    @admin.action(description=_("آرشیو کردن مقالات انتخاب شده"))
    def make_archived(self, request, queryset):
        updated = queryset.update(status="archived")
        self.message_user(request, f"{updated} مقاله آرشیو شد.")

    def save_model(self, request, obj, form, change):
        """
        Set author on creation; respect model's own slug/published_at logic.
        """
        if not change and not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)
