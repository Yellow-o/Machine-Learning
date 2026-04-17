import secrets

from django.db import models
from django.conf import settings
from django.utils import timezone


class UserProfile(models.Model):
    class Role(models.TextChoices):
        DRIVER = "driver", "驾驶员"
        ADMIN = "admin", "管理员"

    class Gender(models.TextChoices):
        UNKNOWN = "unknown", "未知"
        MALE = "male", "男"
        FEMALE = "female", "女"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="账号",
    )
    full_name = models.CharField("姓名", max_length=64, blank=True, default="")
    role = models.CharField(
        "角色",
        max_length=16,
        choices=Role.choices,
        default=Role.DRIVER,
    )
    gender = models.CharField(
        "性别",
        max_length=16,
        choices=Gender.choices,
        default=Gender.UNKNOWN,
    )
    phone = models.CharField("手机号", max_length=20, unique=True, blank=True, default="")
    id_card = models.CharField("身份证号", max_length=32, unique=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "账号信息"
        verbose_name_plural = "账号信息"

    def __str__(self):
        return f"{self.user.username} / {self.full_name or self.id_card}"


class InviteCode(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "管理员"

    code = models.CharField("邀请码", max_length=32, unique=True, blank=True)
    role = models.CharField("用途角色", max_length=16, choices=Role.choices, default=Role.ADMIN)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invite_codes",
        verbose_name="创建人",
    )
    is_active = models.BooleanField("启用", default=True)
    max_uses = models.PositiveIntegerField("最大可用次数", default=1)
    used_count = models.PositiveIntegerField("已使用次数", default=0)
    expires_at = models.DateTimeField("过期时间", null=True, blank=True)
    note = models.CharField("备注", max_length=120, blank=True, default="")
    last_used_at = models.DateTimeField("最近使用时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "邀请码"
        verbose_name_plural = "邀请码"

    @staticmethod
    def generate_code(length=8):
        charset = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return "".join(secrets.choice(charset) for _ in range(length))

    @property
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)

    @property
    def remaining_uses(self):
        return max(0, self.max_uses - self.used_count)

    def is_usable(self):
        return self.is_active and (not self.is_expired) and self.remaining_uses > 0

    def consume(self):
        self.used_count += 1
        self.last_used_at = timezone.now()
        if self.used_count >= self.max_uses:
            self.is_active = False
        self.save(update_fields=["used_count", "last_used_at", "is_active"])

    def __str__(self):
        return f"{self.code} ({self.get_role_display()})"


class Driver(models.Model):
    name = models.CharField("姓名", max_length=64, unique=True)
    id_card = models.CharField("身份证号", max_length=32, blank=True, null=True, unique=True)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "驾驶员"
        verbose_name_plural = "驾驶员"

    def __str__(self):
        return self.name


class DrivingEvent(models.Model):
    class EventType(models.TextChoices):
        FATIGUE = "fatigue", "疲劳驾驶"

    class ReviewStatus(models.TextChoices):
        AUTO = "auto", "系统判定"
        PENDING = "pending", "待复核"
        CONFIRMED = "confirmed", "复核后确认疲劳"
        FALSE_POSITIVE = "false_positive", "复核后判定误报"

    driver = models.ForeignKey(
        Driver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
        verbose_name="驾驶员",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driving_events",
        verbose_name="所属账号",
    )
    event_type = models.CharField(
        "事件类型",
        max_length=32,
        choices=EventType.choices,
        default=EventType.FATIGUE,
    )
    source_event_id = models.CharField(
        "来源事件ID", max_length=64, blank=True, null=True, unique=True
    )
    source_session_id = models.CharField(
        "来源会话ID", max_length=64, blank=True, default=""
    )
    source_label = models.CharField("模型标签", max_length=64, blank=True, default="")
    start_time = models.DateTimeField("开始时间")
    end_time = models.DateTimeField("结束时间")
    duration_sec = models.FloatField("持续秒数", default=0.0)
    peak_risk_conf = models.FloatField("峰值风险置信度", default=0.0)
    trigger_frames = models.PositiveIntegerField("触发帧阈值", default=12)
    recover_frames = models.PositiveIntegerField("恢复帧阈值", default=10)
    snapshot_path = models.CharField("截图路径", max_length=255, blank=True, default="")
    snapshot_sha256 = models.CharField(
        "截图哈希(SHA256)", max_length=64, blank=True, default=""
    )
    review_status = models.CharField(
        "复核状态",
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.AUTO,
    )
    review_note = models.CharField("复核备注", max_length=255, blank=True, default="")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_driving_events",
        verbose_name="复核人",
    )
    reviewed_at = models.DateTimeField("复核时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["-start_time"]
        verbose_name = "疲劳事件"
        verbose_name_plural = "疲劳事件"
        indexes = [
            models.Index(fields=["-start_time"]),
            models.Index(fields=["event_type", "-start_time"]),
            models.Index(fields=["source_session_id"]),
        ]

    def __str__(self):
        driver_name = self.driver.name if self.driver else "Unknown"
        return (
            f"{driver_name} {self.get_event_type_display()} @ "
            f"{self.start_time:%Y-%m-%d %H:%M:%S}"
        )

    @property
    def display_driver_name(self):
        if self.owner_id:
            profile = getattr(self.owner, "profile", None)
            if profile and profile.full_name:
                return profile.full_name
            if self.owner.username:
                return self.owner.username
        if self.driver_id and self.driver:
            return self.driver.name
        return "Unknown"


class DrivingSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "进行中"
        ENDED = "ended", "已结束"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driving_sessions",
        verbose_name="所属账号",
    )
    source_session_id = models.CharField("来源会话ID", max_length=64, unique=True)
    started_at = models.DateTimeField("开始时间")
    ended_at = models.DateTimeField("结束时间", null=True, blank=True)
    duration_sec = models.FloatField("驾驶总时长(秒)", default=0.0)
    source = models.CharField("来源", max_length=32, blank=True, default="gui")
    status = models.CharField(
        "状态",
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "驾驶会话"
        verbose_name_plural = "驾驶会话"
        indexes = [
            models.Index(fields=["-started_at"]),
            models.Index(fields=["status", "-started_at"]),
        ]

    def __str__(self):
        owner_name = self.owner.username if self.owner_id else "Unknown"
        return f"{owner_name} {self.source_session_id}"
