import base64
import csv
import hashlib
import json
import os
import uuid
from datetime import timedelta
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import SignUpForm, UidPhoneAuthenticationForm, resolve_username_from_login_id
from .models import DrivingEvent, DrivingSession, UserProfile


def _event_type_from_label(label: str):
    _ = str(label).lower()
    return DrivingEvent.EventType.FATIGUE


def _is_admin_user(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and profile.role == UserProfile.Role.ADMIN)


class RoleBasedLoginView(LoginView):
    template_name = "monitoring/login.html"
    authentication_form = UidPhoneAuthenticationForm

    def get_success_url(self):
        if _is_admin_user(self.request.user):
            return reverse("dashboard")
        return reverse("records-page")


def _parse_dt(value: str):
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
        except ValueError:
            continue
    return None


def _save_snapshot_from_payload(data: dict, source_event_id: str):
    snapshot_base64 = str(data.get("snapshot_base64") or "").strip()
    if not snapshot_base64:
        return str(data.get("snapshot_path") or "").strip(), str(
            data.get("snapshot_sha256") or ""
        ).strip().lower()

    # Guardrails: reject oversized payloads early.
    if len(snapshot_base64) > 8 * 1024 * 1024:
        raise ValueError("snapshot payload too large")

    try:
        raw = base64.b64decode(snapshot_base64, validate=True)
    except Exception as exc:
        raise ValueError("invalid snapshot_base64") from exc

    if not raw:
        raise ValueError("empty snapshot")
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("snapshot too large")

    digest = hashlib.sha256(raw).hexdigest()
    claimed_digest = str(data.get("snapshot_sha256") or "").strip().lower()
    if claimed_digest and claimed_digest != digest:
        raise ValueError("snapshot_sha256 mismatch")

    filename_hint = str(data.get("snapshot_filename") or "").strip()
    suffix = Path(filename_hint).suffix.lower() if filename_hint else ""
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"

    day_folder = timezone.localtime().strftime("%Y%m%d")
    relative_dir = Path("evidence") / day_folder
    absolute_dir = Path(settings.MEDIA_ROOT) / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{source_event_id}_{digest[:12]}{suffix}"
    absolute_path = absolute_dir / stored_name
    with open(absolute_path, "wb") as f:
        f.write(raw)

    media_path = f"{settings.MEDIA_URL.rstrip('/')}/{(relative_dir / stored_name).as_posix()}"
    return media_path, digest


def _events_base_queryset(user):
    events = (
        DrivingEvent.objects.select_related("driver", "owner", "owner__profile")
        .filter(event_type=DrivingEvent.EventType.FATIGUE)
        .order_by("-start_time")
    )
    if not _is_admin_user(user):
        events = events.filter(owner=user)
    return events


def _safe_int(value, default=0, *, min_value=None, max_value=None):
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if min_value is not None:
        result = max(min_value, result)
    if max_value is not None:
        result = min(max_value, result)
    return result


def _safe_float(value, default=None, *, min_value=None, max_value=None):
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    if min_value is not None:
        result = max(min_value, result)
    if max_value is not None:
        result = min(max_value, result)
    return result


def _serialize_event(event: DrivingEvent):
    return {
        "id": event.id,
        "driver_name": event.display_driver_name,
        "event_type": event.event_type,
        "event_type_display": event.get_event_type_display(),
        "source_event_id": event.source_event_id,
        "source_session_id": event.source_session_id,
        "source_label": event.source_label,
        "start_time": event.start_time.isoformat(),
        "end_time": event.end_time.isoformat(),
        "duration_sec": event.duration_sec,
        "peak_risk_conf": event.peak_risk_conf,
        "review_status": event.review_status,
        "review_status_display": event.get_review_status_display(),
        "trigger_frames": event.trigger_frames,
        "recover_frames": event.recover_frames,
        "snapshot_path": event.snapshot_path,
        "snapshot_sha256": event.snapshot_sha256,
        "owner_username": event.owner.username if event.owner_id else "",
    }


def _serialize_trend(events_qs, days: int):
    today = timezone.localdate()
    day_list = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    start_day = day_list[0]
    rows = (
        events_qs.filter(start_time__date__gte=start_day)
        .annotate(day=TruncDate("start_time"))
        .values("day")
        .annotate(
            event_count=Count("id"),
            duration_sec=Sum("duration_sec"),
            avg_conf=Avg("peak_risk_conf"),
        )
        .order_by("day")
    )
    row_map = {row["day"]: row for row in rows}
    trend = []
    for day in day_list:
        row = row_map.get(day)
        trend.append(
            {
                "day": day.isoformat(),
                "event_count": int((row or {}).get("event_count") or 0),
                "duration_sec": round(float((row or {}).get("duration_sec") or 0.0), 2),
                "avg_conf": round(float((row or {}).get("avg_conf") or 0.0), 3),
            }
        )
    return trend


def _build_records_queryset(request: HttpRequest, is_admin: bool):
    events = (
        DrivingEvent.objects.select_related("driver", "owner", "owner__profile")
        .filter(event_type=DrivingEvent.EventType.FATIGUE)
        .order_by("-start_time")
    )
    if not is_admin:
        events = events.filter(owner=request.user)

    owner_kw = (request.GET.get("owner") or "").strip()
    if is_admin and owner_kw:
        events = events.filter(
            Q(owner__username__icontains=owner_kw)
            | Q(owner__profile__full_name__icontains=owner_kw)
        )

    start_date = (request.GET.get("start_date") or "").strip()
    if start_date:
        events = events.filter(start_time__date__gte=start_date)

    end_date = (request.GET.get("end_date") or "").strip()
    if end_date:
        events = events.filter(start_time__date__lte=end_date)

    min_conf = (request.GET.get("min_conf") or "").strip()
    if is_admin and min_conf:
        try:
            events = events.filter(peak_risk_conf__gte=float(min_conf))
        except ValueError:
            min_conf = ""
    else:
        min_conf = ""

    review_status = (request.GET.get("review_status") or "").strip()
    valid_review_status = {choice[0] for choice in DrivingEvent.ReviewStatus.choices}
    if review_status in valid_review_status:
        events = events.filter(review_status=review_status)
    else:
        review_status = ""

    filters = {
        "owner_filter": owner_kw if is_admin else "",
        "start_date": start_date,
        "end_date": end_date,
        "min_conf": min_conf,
        "review_status": review_status,
    }
    return events, filters


def _build_sessions_queryset(request: HttpRequest, is_admin: bool):
    sessions = DrivingSession.objects.select_related("owner", "owner__profile").order_by(
        "-started_at"
    )
    if not is_admin:
        sessions = sessions.filter(owner=request.user)

    owner_kw = (request.GET.get("owner") or "").strip()
    if is_admin and owner_kw:
        sessions = sessions.filter(
            Q(owner__username__icontains=owner_kw)
            | Q(owner__profile__full_name__icontains=owner_kw)
        )

    start_date = (request.GET.get("start_date") or "").strip()
    if start_date:
        sessions = sessions.filter(started_at__date__gte=start_date)

    end_date = (request.GET.get("end_date") or "").strip()
    if end_date:
        sessions = sessions.filter(started_at__date__lte=end_date)
    return sessions


def _sum_session_seconds_in_window(sessions, window_start, window_end, now_dt):
    total = 0.0
    for session in sessions:
        start = session.started_at
        end = session.ended_at or now_dt
        if end <= window_start or start >= window_end:
            continue
        overlap_start = max(start, window_start)
        overlap_end = min(end, window_end)
        if overlap_end > overlap_start:
            total += (overlap_end - overlap_start).total_seconds()
    return total


def _sum_session_seconds(sessions, now_dt):
    total = 0.0
    for session in sessions:
        end = session.ended_at or now_dt
        if end > session.started_at:
            total += (end - session.started_at).total_seconds()
    return total


def home(request: HttpRequest):
    if request.user.is_authenticated:
        return redirect("/dashboard/")
    return redirect("/login/")


def signup(request: HttpRequest):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            return redirect(f"/login/?uid={user.username}")
    else:
        form = SignUpForm()
    return render(request, "monitoring/signup.html", {"form": form})


def health(request: HttpRequest):
    return JsonResponse(
        {
            "status": "ok",
            "service": "dms_backend",
            "time": timezone.now().isoformat(),
        }
    )


@csrf_exempt
@require_POST
def api_login(request: HttpRequest):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    login_id = str(data.get("username") or data.get("login_id") or "").strip()
    password = str(data.get("password") or "")
    if not login_id or not password:
        return JsonResponse({"error": "login_id and password required"}, status=400)

    username = resolve_username_from_login_id(login_id)
    user = authenticate(username=username, password=password)
    if user is None:
        return JsonResponse({"error": "invalid credentials"}, status=401)

    auth_login(request, user)

    display_name = user.first_name or user.get_full_name() or user.username
    profile = getattr(user, "profile", None)
    if profile and profile.full_name:
        display_name = profile.full_name

    is_admin = _is_admin_user(user)
    role = UserProfile.Role.ADMIN if is_admin else UserProfile.Role.DRIVER

    return JsonResponse(
        {
            "ok": True,
            "username": user.username,
            "display_name": display_name,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "role": role,
            "can_access_dashboard": is_admin,
        }
    )


@login_required
def dashboard(request: HttpRequest):
    if not _is_admin_user(request.user):
        return redirect("records-page")

    events_qs = DrivingEvent.objects.filter(event_type=DrivingEvent.EventType.FATIGUE)
    if not _is_admin_user(request.user):
        events_qs = events_qs.filter(owner=request.user)

    today = timezone.localdate()
    tz = timezone.get_current_timezone()
    today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()), tz)
    today_end = today_start + timedelta(days=1)
    now_dt = timezone.now()
    today_events = events_qs.filter(start_time__date=today)
    today_count = today_events.count()
    today_duration = today_events.aggregate(total=Sum("duration_sec"))["total"] or 0.0
    today_peak = today_events.aggregate(v=Max("peak_risk_conf"))["v"] or 0.0

    sessions_qs = DrivingSession.objects.select_related("owner", "owner__profile")
    if not _is_admin_user(request.user):
        sessions_qs = sessions_qs.filter(owner=request.user)
    sessions_qs = sessions_qs.filter(started_at__lt=today_end).filter(
        Q(ended_at__isnull=True) | Q(ended_at__gt=today_start)
    )
    today_drive_seconds = _sum_session_seconds_in_window(
        sessions=sessions_qs.iterator(),
        window_start=today_start,
        window_end=today_end,
        now_dt=now_dt,
    )
    fatigue_ratio_pct = (
        (today_duration / today_drive_seconds) * 100.0 if today_drive_seconds > 0 else 0.0
    )

    recent_events = (
        events_qs.select_related("driver", "owner", "owner__profile")
        .order_by("-start_time")[:10]
    )

    days_ago = today - timedelta(days=6)
    trend_rows = (
        events_qs.filter(start_time__date__gte=days_ago)
        .annotate(day=TruncDate("start_time"))
        .values("day")
        .annotate(count=Count("id"), duration=Sum("duration_sec"))
        .order_by("day")
    )
    trend = [
        {
            "day": r["day"],
            "count": r["count"],
            "duration": round(float(r["duration"] or 0.0), 2),
        }
        for r in trend_rows
    ]
    top_accounts = (
        events_qs.values("owner__username", "owner__profile__full_name")
        .annotate(
            event_count=Count("id"),
            total_duration=Sum("duration_sec"),
            max_conf=Max("peak_risk_conf"),
        )
        .order_by("-event_count", "-total_duration")[:5]
    )
    review_stats = events_qs.values("review_status").annotate(total=Count("id"))
    review_count = {row["review_status"]: row["total"] for row in review_stats}
    profile_stats = UserProfile.objects.values("role").annotate(total=Count("id"))
    role_count = {row["role"]: row["total"] for row in profile_stats}

    context = {
        "is_admin": _is_admin_user(request.user),
        "today": today,
        "today_count": today_count,
        "today_duration": round(today_duration, 2),
        "today_drive_seconds": round(float(today_drive_seconds), 2),
        "today_fatigue_ratio": round(float(fatigue_ratio_pct), 2),
        "today_peak": round(float(today_peak), 3),
        "recent_events": recent_events,
        "trend": trend,
        "top_accounts": top_accounts,
        "pending_review_count": review_count.get(DrivingEvent.ReviewStatus.PENDING, 0),
        "auto_count": review_count.get(DrivingEvent.ReviewStatus.AUTO, 0),
        "confirmed_count": review_count.get(DrivingEvent.ReviewStatus.CONFIRMED, 0),
        "false_positive_count": review_count.get(
            DrivingEvent.ReviewStatus.FALSE_POSITIVE, 0
        ),
        "account_count": role_count.get(UserProfile.Role.DRIVER, 0)
        + role_count.get(UserProfile.Role.ADMIN, 0),
        "driver_count": role_count.get(UserProfile.Role.DRIVER, 0),
        "admin_count": role_count.get(UserProfile.Role.ADMIN, 0),
    }
    return render(request, "monitoring/dashboard.html", context)


@login_required
def records_page(request: HttpRequest):
    is_admin = _is_admin_user(request.user)
    events, filters = _build_records_queryset(request, is_admin)
    sessions = _build_sessions_queryset(request, is_admin)

    total_events = events.count()
    total_duration = events.aggregate(total=Sum("duration_sec"))["total"] or 0.0
    drive_duration = _sum_session_seconds(
        sessions=sessions.iterator(),
        now_dt=timezone.now(),
    )
    fatigue_ratio = (float(total_duration) / float(drive_duration) * 100.0) if drive_duration else 0.0
    review_stats = events.values("review_status").annotate(total=Count("id"))
    review_count = {row["review_status"]: row["total"] for row in review_stats}
    pending_count = review_count.get(DrivingEvent.ReviewStatus.PENDING, 0)

    review_choices = [
        (DrivingEvent.ReviewStatus.AUTO, DrivingEvent.ReviewStatus.AUTO.label),
        (DrivingEvent.ReviewStatus.CONFIRMED, DrivingEvent.ReviewStatus.CONFIRMED.label),
        (
            DrivingEvent.ReviewStatus.FALSE_POSITIVE,
            DrivingEvent.ReviewStatus.FALSE_POSITIVE.label,
        ),
    ]
    if pending_count > 0 or filters["review_status"] == DrivingEvent.ReviewStatus.PENDING:
        review_choices.insert(
            1, (DrivingEvent.ReviewStatus.PENDING, DrivingEvent.ReviewStatus.PENDING.label)
        )

    context = {
        "events": events[:200],
        "is_admin": is_admin,
        "total_events": total_events,
        "total_duration": round(float(total_duration), 2),
        "drive_duration": round(float(drive_duration), 2),
        "fatigue_ratio": round(float(fatigue_ratio), 2),
        "owner_filter": filters["owner_filter"],
        "start_date": filters["start_date"],
        "end_date": filters["end_date"],
        "min_conf": filters["min_conf"],
        "review_status": filters["review_status"],
        "review_choices": review_choices,
        "pending_count": pending_count,
        "auto_count": review_count.get(DrivingEvent.ReviewStatus.AUTO, 0),
        "confirmed_count": review_count.get(DrivingEvent.ReviewStatus.CONFIRMED, 0),
        "false_positive_count": review_count.get(
            DrivingEvent.ReviewStatus.FALSE_POSITIVE, 0
        ),
        "show_pending": pending_count > 0,
    }
    return render(request, "monitoring/records.html", context)


@login_required
def event_detail_page(request: HttpRequest, event_id: int):
    is_admin = _is_admin_user(request.user)
    events, _ = _build_records_queryset(request, is_admin)
    event = events.filter(id=event_id).first()
    if event is None:
        return redirect("records-page")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if is_admin and action == "review":
            target_status = (request.POST.get("review_status") or "").strip()
            target_note = (request.POST.get("review_note") or "").strip()
            valid_status = {
                DrivingEvent.ReviewStatus.CONFIRMED,
                DrivingEvent.ReviewStatus.FALSE_POSITIVE,
            }
            if (
                event.review_status == DrivingEvent.ReviewStatus.PENDING
                and target_status in valid_status
            ):
                event.review_status = target_status
                event.review_note = target_note[:255]
                event.reviewed_by = request.user
                event.reviewed_at = timezone.now()
                event.save(
                    update_fields=[
                        "review_status",
                        "review_note",
                        "reviewed_by",
                        "reviewed_at",
                    ]
                )
        elif (not is_admin) and action == "appeal":
            appeal_note = (request.POST.get("appeal_note") or "").strip()
            if (
                event.review_status == DrivingEvent.ReviewStatus.AUTO
                and appeal_note
            ):
                event.review_status = DrivingEvent.ReviewStatus.PENDING
                event.review_note = appeal_note[:255]
                event.reviewed_by = None
                event.reviewed_at = None
                event.save(
                    update_fields=[
                        "review_status",
                        "review_note",
                        "reviewed_by",
                        "reviewed_at",
                    ]
                )
        return redirect(f"/records/{event.id}/?saved=1")

    can_preview = str(event.snapshot_path or "").startswith(settings.MEDIA_URL)
    context = {
        "event": event,
        "is_admin": is_admin,
        "can_preview": can_preview,
        "can_appeal": (not is_admin)
        and event.review_status == DrivingEvent.ReviewStatus.AUTO,
        "can_admin_review": is_admin
        and event.review_status == DrivingEvent.ReviewStatus.PENDING,
        "review_choices": [
            (DrivingEvent.ReviewStatus.CONFIRMED, DrivingEvent.ReviewStatus.CONFIRMED.label),
            (
                DrivingEvent.ReviewStatus.FALSE_POSITIVE,
                DrivingEvent.ReviewStatus.FALSE_POSITIVE.label,
            ),
        ],
        "saved": request.GET.get("saved") == "1",
    }
    return render(request, "monitoring/event_detail.html", context)


@login_required
def export_records_csv(request: HttpRequest):
    is_admin = _is_admin_user(request.user)
    events, _ = _build_records_queryset(request, is_admin)

    now = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="fatigue_records_{now}.csv"'

    response.write("\ufeff")
    writer = csv.writer(response)
    if is_admin:
        writer.writerow(
            [
                "事件ID",
                "会话ID",
                "开始时间",
                "结束时间",
                "账号姓名",
                "账号UID",
                "类型",
                "复核状态",
                "复核人",
                "复核时间",
                "复核备注",
                "标签",
                "时长(秒)",
                "峰值置信度",
                "截图路径",
                "截图哈希",
            ]
        )
    else:
        writer.writerow(
            [
                "事件ID",
                "会话ID",
                "开始时间",
                "结束时间",
                "类型",
                "复核状态",
                "时长(秒)",
                "截图路径",
            ]
        )

    for event in events.iterator():
        if is_admin:
            writer.writerow(
                [
                    event.id,
                    event.source_session_id,
                    event.start_time,
                    event.end_time,
                    event.display_driver_name,
                    event.owner.username if event.owner_id else "",
                    event.get_event_type_display(),
                    event.get_review_status_display(),
                    event.reviewed_by.username if event.reviewed_by_id else "",
                    event.reviewed_at or "",
                    event.review_note,
                    event.source_label,
                    round(float(event.duration_sec), 2),
                    round(float(event.peak_risk_conf), 3),
                    event.snapshot_path,
                    event.snapshot_sha256,
                ]
            )
        else:
            writer.writerow(
                [
                    event.id,
                    event.source_session_id,
                    event.start_time,
                    event.end_time,
                    event.get_event_type_display(),
                    event.get_review_status_display(),
                    round(float(event.duration_sec), 2),
                    event.snapshot_path,
                ]
            )
    return response


@login_required
def recent_events_api(request: HttpRequest):
    limit = _safe_int(request.GET.get("limit"), default=50, min_value=1, max_value=100)
    events = _events_base_queryset(request.user)[:limit]
    payload = [_serialize_event(event) for event in events]
    return JsonResponse(payload, safe=False)


@login_required
def events_list_api(request: HttpRequest):
    events = _events_base_queryset(request.user)
    keyword = (request.GET.get("q") or "").strip()
    review_status = (request.GET.get("review_status") or "").strip()
    start_date = (request.GET.get("start_date") or "").strip()
    end_date = (request.GET.get("end_date") or "").strip()
    min_conf = _safe_float(request.GET.get("min_conf"), default=None, min_value=0.0, max_value=1.0)

    if keyword:
        events = events.filter(
            Q(owner__username__icontains=keyword)
            | Q(owner__profile__full_name__icontains=keyword)
            | Q(source_label__icontains=keyword)
            | Q(source_session_id__icontains=keyword)
            | Q(source_event_id__icontains=keyword)
        )

    valid_review_status = {choice[0] for choice in DrivingEvent.ReviewStatus.choices}
    if review_status in valid_review_status:
        events = events.filter(review_status=review_status)
    else:
        review_status = ""

    if start_date:
        events = events.filter(start_time__date__gte=start_date)
    if end_date:
        events = events.filter(start_time__date__lte=end_date)
    if min_conf is not None:
        events = events.filter(peak_risk_conf__gte=min_conf)

    total = events.count()
    stats = events.aggregate(
        total_duration=Sum("duration_sec"),
        avg_conf=Avg("peak_risk_conf"),
        max_conf=Max("peak_risk_conf"),
    )
    review_stats = events.values("review_status").annotate(total=Count("id"))
    review_count = {row["review_status"]: row["total"] for row in review_stats}

    page = _safe_int(request.GET.get("page"), default=1, min_value=1)
    page_size = _safe_int(request.GET.get("page_size"), default=20, min_value=5, max_value=100)
    paginator = Paginator(events, page_size)
    page_obj = paginator.get_page(page)
    items = [_serialize_event(event) for event in page_obj.object_list]

    return JsonResponse(
        {
            "items": items,
            "summary": {
                "total": total,
                "total_duration_sec": round(float(stats.get("total_duration") or 0.0), 2),
                "avg_conf": round(float(stats.get("avg_conf") or 0.0), 3),
                "max_conf": round(float(stats.get("max_conf") or 0.0), 3),
                "pending_count": review_count.get(DrivingEvent.ReviewStatus.PENDING, 0),
                "confirmed_count": review_count.get(DrivingEvent.ReviewStatus.CONFIRMED, 0),
                "false_positive_count": review_count.get(
                    DrivingEvent.ReviewStatus.FALSE_POSITIVE, 0
                ),
                "auto_count": review_count.get(DrivingEvent.ReviewStatus.AUTO, 0),
            },
            "pagination": {
                "page": page_obj.number,
                "page_size": page_size,
                "total": total,
                "total_pages": paginator.num_pages or 1,
            },
            "filters": {
                "q": keyword,
                "review_status": review_status,
                "start_date": start_date,
                "end_date": end_date,
                "min_conf": min_conf,
            },
            "meta": {
                "is_admin": _is_admin_user(request.user),
            },
        }
    )


@login_required
def dashboard_overview_api(request: HttpRequest):
    days = _safe_int(request.GET.get("days"), default=7)
    if days not in {7, 30}:
        days = 7

    events = _events_base_queryset(request.user)
    trend = _serialize_trend(events, days=days)
    period_start = timezone.localdate() - timedelta(days=days - 1)
    period_events = events.filter(start_time__date__gte=period_start)

    metrics = period_events.aggregate(
        total_duration=Sum("duration_sec"),
        avg_conf=Avg("peak_risk_conf"),
        max_conf=Max("peak_risk_conf"),
    )
    high_risk_count = period_events.filter(peak_risk_conf__gte=0.8).count()
    review_stats = period_events.values("review_status").annotate(total=Count("id"))
    review_count = {row["review_status"]: row["total"] for row in review_stats}
    recent_events = [_serialize_event(event) for event in period_events[:8]]

    return JsonResponse(
        {
            "window_days": days,
            "kpis": {
                "total_events": period_events.count(),
                "total_duration_sec": round(float(metrics.get("total_duration") or 0.0), 2),
                "avg_conf": round(float(metrics.get("avg_conf") or 0.0), 3),
                "max_conf": round(float(metrics.get("max_conf") or 0.0), 3),
                "high_risk_count": high_risk_count,
                "pending_count": review_count.get(DrivingEvent.ReviewStatus.PENDING, 0),
                "confirmed_count": review_count.get(DrivingEvent.ReviewStatus.CONFIRMED, 0),
                "false_positive_count": review_count.get(
                    DrivingEvent.ReviewStatus.FALSE_POSITIVE, 0
                ),
                "auto_count": review_count.get(DrivingEvent.ReviewStatus.AUTO, 0),
            },
            "trend": trend,
            "recent_events": recent_events,
            "meta": {
                "is_admin": _is_admin_user(request.user),
            },
        }
    )


@csrf_exempt
@require_POST
def event_report_api(request: HttpRequest):
    expected_token = os.getenv("DMS_INGEST_TOKEN", "").strip()
    if expected_token:
        provided_token = request.headers.get("X-DMS-Token", "").strip()
        if provided_token != expected_token:
            return JsonResponse({"error": "unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    start_time = _parse_dt(data.get("start_time"))
    end_time = _parse_dt(data.get("end_time"))
    if not start_time or not end_time:
        return JsonResponse({"error": "invalid start_time or end_time"}, status=400)

    source_event_id = str(
        data.get("source_event_id") or data.get("event_id") or uuid.uuid4().hex
    ).strip()
    source_session_id = str(data.get("source_session_id") or "").strip()
    source_label = str(data.get("source_label") or "").strip()
    owner_username = str(data.get("account_username") or "").strip()
    event_type = str(data.get("event_type") or "").strip().lower()
    if event_type != DrivingEvent.EventType.FATIGUE:
        event_type = _event_type_from_label(source_label)

    owner = None
    if owner_username:
        owner = User.objects.filter(username=owner_username).first()

    duration_sec = data.get("duration_sec")
    if duration_sec is None:
        duration_sec = max(0.0, (end_time - start_time).total_seconds())
    else:
        duration_sec = float(duration_sec)

    try:
        snapshot_path, snapshot_sha256 = _save_snapshot_from_payload(data, source_event_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    event, created = DrivingEvent.objects.update_or_create(
        source_event_id=source_event_id,
        defaults={
            "owner": owner,
            "event_type": event_type,
            "source_label": source_label,
            "source_session_id": source_session_id,
            "start_time": start_time,
            "end_time": end_time,
            "duration_sec": duration_sec,
            "peak_risk_conf": float(data.get("peak_risk_conf") or 0.0),
            "trigger_frames": int(data.get("trigger_frames") or 12),
            "recover_frames": int(data.get("recover_frames") or 10),
            "snapshot_path": snapshot_path,
            "snapshot_sha256": snapshot_sha256,
        },
    )

    return JsonResponse(
        {
            "ok": True,
            "id": event.id,
            "created": created,
            "snapshot_path": snapshot_path,
            "snapshot_sha256": snapshot_sha256,
        }
    )


@csrf_exempt
@require_POST
def session_report_api(request: HttpRequest):
    expected_token = os.getenv("DMS_INGEST_TOKEN", "").strip()
    if expected_token:
        provided_token = request.headers.get("X-DMS-Token", "").strip()
        if provided_token != expected_token:
            return JsonResponse({"error": "unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    source_session_id = str(
        data.get("source_session_id") or data.get("session_id") or ""
    ).strip()
    action = str(data.get("action") or "").strip().lower()
    if not source_session_id:
        return JsonResponse({"error": "source_session_id required"}, status=400)
    if action not in {"start", "end"}:
        return JsonResponse({"error": "action must be start or end"}, status=400)

    owner = None
    owner_username = str(data.get("account_username") or "").strip()
    if owner_username:
        owner = User.objects.filter(username=owner_username).first()

    if action == "start":
        start_time = _parse_dt(data.get("start_time")) or timezone.now()
        session, created = DrivingSession.objects.update_or_create(
            source_session_id=source_session_id,
            defaults={
                "owner": owner,
                "started_at": start_time,
                "ended_at": None,
                "duration_sec": 0.0,
                "source": str(data.get("source") or "gui")[:32],
                "status": DrivingSession.Status.ACTIVE,
            },
        )
        return JsonResponse(
            {
                "ok": True,
                "created": created,
                "id": session.id,
                "status": session.status,
            }
        )

    # action == end
    session = DrivingSession.objects.filter(source_session_id=source_session_id).first()
    if session is None:
        start_time = _parse_dt(data.get("start_time")) or timezone.now()
        session = DrivingSession.objects.create(
            owner=owner,
            source_session_id=source_session_id,
            started_at=start_time,
            source=str(data.get("source") or "gui")[:32],
        )

    end_time = _parse_dt(data.get("end_time")) or timezone.now()
    if end_time < session.started_at:
        end_time = session.started_at
    duration_sec = float(data.get("duration_sec") or 0.0)
    if duration_sec <= 0:
        duration_sec = max(0.0, (end_time - session.started_at).total_seconds())

    session.ended_at = end_time
    session.duration_sec = duration_sec
    session.status = DrivingSession.Status.ENDED
    if owner and not session.owner_id:
        session.owner = owner
    session.save(
        update_fields=["owner", "ended_at", "duration_sec", "status", "updated_at"]
    )

    return JsonResponse(
        {
            "ok": True,
            "id": session.id,
            "status": session.status,
            "duration_sec": round(float(session.duration_sec), 2),
        }
    )
