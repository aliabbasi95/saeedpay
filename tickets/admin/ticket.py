# tickets/admin/ticket.py

from django.contrib import admin
from django.db.models import Count, Subquery, OuterRef
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from lib.erp_base.admin import BaseAdmin, BaseStackedInlineAdmin
from tickets.models import Ticket, TicketMessage


class TicketMessageInline(BaseStackedInlineAdmin):
    model = TicketMessage
    fields = ("content", "reply_to")
    extra = 0
    can_delete = False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "reply_to":
            object_id = getattr(
                getattr(request, "resolver_match", None), "kwargs", {}
            ).get("object_id")
            qs = TicketMessage.objects.filter(
                ticket_id=object_id
            ) if object_id else TicketMessage.objects.none()
            kwargs["queryset"] = qs
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class HasAssigneeFilter(admin.SimpleListFilter):
    title = _("مسئول دارد؟")
    parameter_name = "assigned"

    def lookups(self, request, model_admin):
        return (("yes", _("بله")), ("no", _("خیر")),)

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(assigned_staff__isnull=False)
        if self.value() == "no":
            return queryset.filter(assigned_staff__isnull=True)
        return queryset


class HasWaitingOnUserFlagFilter(admin.SimpleListFilter):
    title = _("در انتظار کاربر/تیم؟")
    parameter_name = "waiting"

    def lookups(self, request, model_admin):
        return (
            ("user", _("در انتظار کاربر")),
            ("staff", _("در انتظار پشتیبانی")),
        )

    def queryset(self, request, qs):
        if self.value() == "user":
            return qs.filter(status=Ticket.Status.WAITING_ON_USER)
        if self.value() == "staff":
            return qs.filter(
                status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS,
                            Ticket.Status.REOPENED]
            )
        return qs


@admin.register(Ticket)
class TicketAdmin(BaseAdmin):
    list_display = (
        "id",
        "title",
        "user_link",
        "assignee_badge",
        "status_badge",
        "priority_badge",
        "category",
        "messages_count",
        "last_message_preview",
        "jalali_update_date_time",
    )
    list_filter = ("status", "priority", "category", HasAssigneeFilter,
                   HasWaitingOnUserFlagFilter)
    search_fields = ("id", "title", "user__username",
                     "assigned_staff__username")
    inlines = [TicketMessageInline]
    list_select_related = ("user", "assigned_staff", "category")
    list_per_page = 30
    ordering = ("-id",)
    autocomplete_fields = ("user", "assigned_staff", "category")

    fieldsets = (
        (None, {"fields": ("user", "title", "category")}),
        (_("وضعیت"), {"fields": ("status", "priority", "assigned_staff")}),
    )

    actions = (
        "action_mark_in_progress",
        "action_mark_waiting_on_user",
        "action_mark_resolved",
        "action_reopen",
        "action_close",
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            "category", "user", "assigned_staff"
        )
        qs = qs.annotate(_messages_count=Count("messages"))
        last_msg = TicketMessage.objects.filter(
            ticket=OuterRef("pk")
        ).order_by("-id").values("content")[:1]
        qs = qs.annotate(_last_msg=Subquery(last_msg))
        return qs

    @admin.display(description=_("کاربر"))
    def user_link(self, obj: Ticket):
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>', obj.user_id,
            obj.user.username
        )

    @admin.display(description=_("مسئول"))
    def assignee_badge(self, obj: Ticket):
        if not obj.assigned_staff:
            return format_html('<span style="color:#888">-</span>')
        return format_html(
            '<a href="/admin/auth/user/{}/change/"><span style="padding:.1rem .4rem;'
            'border-radius:.35rem;background:#e3f2fd;color:#1565c0">{}</span></a>',
            obj.assigned_staff_id, obj.assigned_staff.username
        )

    @admin.display(description=_("وضعیت"))
    def status_badge(self, obj: Ticket):
        palette = {
            Ticket.Status.OPEN: "#6d4c41",
            Ticket.Status.IN_PROGRESS: "#1769aa",
            Ticket.Status.WAITING_ON_USER: "#f57c00",
            Ticket.Status.RESOLVED: "#2e7d32",
            Ticket.Status.REOPENED: "#7b1fa2",
            Ticket.Status.CLOSED: "#455a64",
        }
        label = dict(Ticket.Status.choices).get(obj.status, obj.status)
        return format_html(
            '<span style="padding:.15rem .45rem;border-radius:.4rem;'
            'font-size:.75rem;color:#fff;background:{}">{}</span>',
            palette.get(obj.status, "#616161"), label
        )

    @admin.display(description=_("اولویت"))
    def priority_badge(self, obj: Ticket):
        tone = {
            Ticket.Priority.LOW: "#78909c",
            Ticket.Priority.NORMAL: "#546e7a",
            Ticket.Priority.HIGH: "#f4511e",
            Ticket.Priority.URGENT: "#c62828",
        }
        label = dict(Ticket.Priority.choices).get(obj.priority, obj.priority)
        return format_html(
            '<span style="padding:.1rem .35rem;border-radius:.35rem;'
            'font-size:.75rem;color:#fff;background:{}">{}</span>',
            tone.get(obj.priority, "#607d8b"), label
        )

    @admin.display(description=_("تعداد پیام‌ها"))
    def messages_count(self, obj: Ticket) -> int:
        return getattr(obj, "_messages_count", obj.messages.count())

    @admin.display(description=_("آخرین پیام"))
    def last_message_preview(self, obj: Ticket):
        txt = (obj._last_msg or "") if hasattr(obj, "_last_msg") else ""
        return (txt[:36] + "…") if txt and len(txt) > 36 else (txt or "-")

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = ("user", "title")
        if not request.user.is_superuser:
            readonly_fields += ("status",)
        return readonly_fields

    def _bulk_set_status(self, request, queryset, new_status, success_msg):
        updated = 0
        for t in queryset:
            if t.status != new_status:
                t.status = new_status
                updated += 1
                t.save(update_fields=["status", "updated_at"])
        self.message_user(request, success_msg.format(updated=updated))

    # --- Actions ---
    def _update_many(self, request, queryset, status_value, success_message):
        updated = 0
        for t in queryset:
            if t.status != status_value:
                t.status = status_value
                t.save()
                updated += 1
        self.message_user(request, success_message.format(updated=updated))

    @admin.action(description=_("علامت‌گذاری به در حال رسیدگی"))
    def action_mark_in_progress(self, request, queryset):
        self._update_many(
            request,
            queryset,
            Ticket.Status.IN_PROGRESS,
            _("{updated} تیکت در حال رسیدگی شد."),
        )

    @admin.action(description=_("علامت‌گذاری به در انتظار کاربر"))
    def action_mark_waiting_on_user(self, request, queryset):
        self._update_many(
            request,
            queryset,
            Ticket.Status.WAITING_ON_USER,
            _("{updated} تیکت به در انتظار کاربر تغییر کرد."),
        )

    @admin.action(description=_("علامت‌گذاری به حل شد"))
    def action_mark_resolved(self, request, queryset):
        self._update_many(
            request,
            queryset,
            Ticket.Status.RESOLVED,
            _("{updated} تیکت حل شد."),
        )

    @admin.action(description=_("بازگشایی تیکت"))
    def action_reopen(self, request, queryset):
        self._update_many(
            request,
            queryset,
            Ticket.Status.REOPENED,
            _("{updated} تیکت دوباره باز شد."),
        )

    @admin.action(description=_("بستن تیکت"))
    def action_close(self, request, queryset):
        self._update_many(
            request,
            queryset,
            Ticket.Status.CLOSED,
            _("{updated} تیکت بسته شد."),
        )

    def save_formset(self, request, form, formset, change):
        if formset.model is TicketMessage:
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()
            for instance in instances:
                if instance.pk:
                    continue
                instance.sender = TicketMessage.Sender.STAFF
                instance.creator = request.user
                instance.save()
                self._on_staff_reply(instance.ticket, request.user)
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)

    def _on_staff_reply(self, ticket: Ticket, staff_user):
        changed = False
        if not ticket.assigned_staff:
            ticket.assigned_staff = staff_user
            changed = True

        if ticket.status in {Ticket.Status.RESOLVED, Ticket.Status.CLOSED}:
            new_status = Ticket.Status.REOPENED
        elif ticket.status in {Ticket.Status.OPEN, Ticket.Status.REOPENED,
                               Ticket.Status.WAITING_ON_USER}:
            new_status = Ticket.Status.IN_PROGRESS
        else:
            new_status = ticket.status

        if new_status != ticket.status:
            ticket.status = new_status
            changed = True

        if changed:
            ticket.save(
                update_fields=["assigned_staff", "status", "updated_at"]
            )
