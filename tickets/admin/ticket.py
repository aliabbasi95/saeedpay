# tickets/admin/ticket.py

from django.contrib import admin
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
            try:
                object_id = request.resolver_match.kwargs.get("object_id")
            except Exception:  # pragma: no cover - defensive
                object_id = None
            if object_id:
                kwargs["queryset"] = TicketMessage.objects.filter(ticket_id=object_id)
            else:
                kwargs["queryset"] = TicketMessage.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request, obj=None):
        # Allow adding replies; module-level permissions handled by BasePermissions
        return True

    def has_change_permission(self, request, obj=None):
        # Inline edits are not allowed; only adding replies is supported
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(BaseAdmin):
    list_display = (
        "id",
        "title",
        "user",
        "assigned_staff",
        "status",
        "priority",
        "category",
        "messages_count",
        "jalali_update_date_time",
    )
    list_filter = ("status", "priority", "category")
    search_fields = ("title", "user__username")
    inlines = [TicketMessageInline]
    list_select_related = ("user", "assigned_staff", "category")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "user",
                    "title",
                    "status",
                    "priority",
                    "category",
                    "assigned_staff",
                )
            },
        ),
    )

    actions = (
        "action_mark_in_progress",
        "action_mark_waiting_on_user",
        "action_mark_resolved",
        "action_reopen",
        "action_close",
    )

    @admin.display(description=_("تعداد پیام‌ها"))
    def messages_count(self, obj: Ticket) -> int:
        return obj.messages.count()

    def get_readonly_fields(self, request, obj=None):
        # Staff should not alter owner, title, or status directly
        if request.user.is_superuser:
            return ("user", "title")
        return ("user", "title", "status")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        # Allow staff to open ticket detail to reply via inline
        return True

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

    # Ensure replies via inline are saved as staff and update status accordingly
    def save_formset(self, request, form, formset, change):
        if formset.model is TicketMessage:
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()
            for instance in instances:
                # Disallow editing existing messages via inline; only allow new replies
                if instance.pk:
                    continue
                # Force staff as sender for replies submitted via admin
                instance.sender = instance.Sender.STAFF
                instance.creator = request.user
                instance.save()
                # Move ticket to in_progress when staff replies
                self._on_staff_reply(instance.ticket, request.user)
            formset.save_m2m()
        else:
            super(TicketAdmin, self).save_formset(request, form, formset, change)

    def _on_staff_reply(self, ticket: Ticket, staff_user):
        # Assign staff if not set and transition status smartly
        changed = False
        if not ticket.assigned_staff:
            ticket.assigned_staff = staff_user
            changed = True

        if ticket.status in {Ticket.Status.RESOLVED, Ticket.Status.CLOSED}:
            new_status = Ticket.Status.REOPENED
        elif ticket.status in {Ticket.Status.OPEN, Ticket.Status.REOPENED, Ticket.Status.WAITING_ON_USER}:
            new_status = Ticket.Status.IN_PROGRESS
        else:
            new_status = ticket.status

        if new_status != ticket.status:
            ticket.status = new_status
            changed = True

        if changed:
            ticket.save()
