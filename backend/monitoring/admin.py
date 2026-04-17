from django.contrib import messages
from django.contrib import admin
from django.utils.html import format_html

from .models import DrivingEvent, DrivingSession, InviteCode, UserProfile


@admin.register(DrivingEvent)
class DrivingEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "owner_display",
        "event_type",
        "review_status",
        "reviewed_by",
        "reviewed_at",
        "start_time",
        "duration_sec",
        "peak_risk_conf",
        "snapshot_sha256",
    )
    list_filter = ("review_status", "start_time")
    search_fields = (
        "owner__username",
        "owner__profile__full_name",
        "source_label",
        "review_note",
        "snapshot_path",
        "snapshot_sha256",
    )
    autocomplete_fields = ("owner",)

    @admin.display(description="账号")
    def owner_display(self, obj):
        return obj.display_driver_name


@admin.register(DrivingSession)
class DrivingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "owner",
        "source_session_id",
        "status",
        "started_at",
        "ended_at",
        "duration_sec",
        "source",
    )
    list_filter = ("status", "started_at", "source")
    search_fields = (
        "owner__username",
        "owner__profile__full_name",
        "source_session_id",
    )
    autocomplete_fields = ("owner",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "full_name",
        "role",
        "gender",
        "phone",
        "id_card",
        "updated_at",
    )
    list_filter = ("role", "gender")
    search_fields = ("user__username", "full_name", "phone", "id_card")
    actions = ("promote_to_admin", "demote_to_driver")

    @admin.action(description="将所选驾驶员晋升为管理员")
    def promote_to_admin(self, request, queryset):
        updated = 0
        for profile in queryset.select_related("user"):
            user = profile.user
            changed = False
            if profile.role != UserProfile.Role.ADMIN:
                profile.role = UserProfile.Role.ADMIN
                profile.save(update_fields=["role"])
                changed = True
            if not user.is_staff:
                user.is_staff = True
                user.save(update_fields=["is_staff"])
                changed = True
            if changed:
                updated += 1
        self.message_user(request, f"已晋升 {updated} 个账号为管理员。", messages.SUCCESS)

    @admin.action(description="将所选管理员降级为驾驶员")
    def demote_to_driver(self, request, queryset):
        updated = 0
        for profile in queryset.select_related("user"):
            user = profile.user
            if user.is_superuser:
                continue
            changed = False
            if profile.role != UserProfile.Role.DRIVER:
                profile.role = UserProfile.Role.DRIVER
                profile.save(update_fields=["role"])
                changed = True
            if user.is_staff:
                user.is_staff = False
                user.save(update_fields=["is_staff"])
                changed = True
            if changed:
                updated += 1
        self.message_user(request, f"已降级 {updated} 个账号为驾驶员。", messages.SUCCESS)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            actions.pop("promote_to_admin", None)
            actions.pop("demote_to_driver", None)
        return actions


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "copy_code",
        "role",
        "is_active",
        "max_uses",
        "used_count",
        "expires_at",
        "created_by",
        "created_at",
    )
    list_filter = ("role", "is_active", "expires_at")
    search_fields = ("code", "note", "created_by__username")
    readonly_fields = ("used_count", "last_used_at", "created_at", "created_by")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="复制")
    def copy_code(self, obj):
        return format_html(
            (
                '<button type="button" style="padding:1px 6px; border-radius:5px; '
                "font-size:12px; line-height:1.3; "
                'border:1px solid #cbd5e1; background:#f8fafc; cursor:pointer; white-space:nowrap;" '
                "onclick=\"navigator.clipboard.writeText('{}');"
                "this.textContent='已复制';"
                "setTimeout(function(){{this.textContent='复制';}}.bind(this),1200);\">复制</button>"
            ),
            obj.code,
        )

    def save_model(self, request, obj, form, change):
        generated = False
        if not obj.code:
            obj.code = InviteCode.generate_code(length=10)
            generated = True
        obj.code = obj.code.strip().upper()
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        if generated:
            self.message_user(
                request,
                f"邀请码已生成：{obj.code}（请复制保存）",
                level=messages.WARNING,
            )

    def get_fields(self, request, obj=None):
        base_fields = (
            "role",
            "is_active",
            "max_uses",
            "used_count",
            "expires_at",
            "note",
            "last_used_at",
            "created_by",
            "created_at",
        )
        if obj:
            return ("code",) + base_fields
        return base_fields

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj:
            fields.append("code")
        return tuple(fields)
