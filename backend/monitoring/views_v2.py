import json
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Max, Q, Sum
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .forms import resolve_username_from_login_id
from .models import DrivingEvent, UserProfile
from .views import _events_base_queryset, _is_admin_user, _safe_float, _safe_int, _serialize_event, _serialize_trend

ERR_AUTH_REQUIRED = 1001
ERR_PERMISSION_DENIED = 1003
ERR_VALIDATION = 1400
ERR_NOT_FOUND = 1404
ERR_CONFLICT = 1409
ERR_SERVER = 1500


@dataclass(frozen=True)
class ApiError(Exception):
    status: int
    code: int
    message: str


def _request_id(request: HttpRequest) -> str:
    return request.headers.get("X-Request-ID") or uuid.uuid4().hex


def _envelope(request: HttpRequest, *, code: int, message: str, data):
    return {
        "code": code,
        "message": message,
        "data": data,
        "request_id": _request_id(request),
        "timestamp": timezone.now().isoformat(),
    }


def _ok(request: HttpRequest, data=None, message: str = "ok"):
    return JsonResponse(_envelope(request, code=0, message=message, data=data or {}))


def _error(request: HttpRequest, *, status: int, code: int, message: str):
    return JsonResponse(_envelope(request, code=code, message=message, data={}), status=status)


def _parse_json(request: HttpRequest) -> dict:
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        value = json.loads(raw)
    except Exception as exc:
        raise ApiError(status=400, code=ERR_VALIDATION, message="invalid json") from exc
    if not isinstance(value, dict):
        raise ApiError(status=400, code=ERR_VALIDATION, message="json body must be an object")
    return value


def _require_auth(request: HttpRequest):
    if not request.user.is_authenticated:
        raise ApiError(status=401, code=ERR_AUTH_REQUIRED, message="authentication required")


def _require_admin(request: HttpRequest):
    _require_auth(request)
    if not _is_admin_user(request.user):
        raise ApiError(status=403, code=ERR_PERMISSION_DENIED, message="admin permission required")


def _role_from_user(user: User) -> str:
    if _is_admin_user(user):
        return UserProfile.Role.ADMIN
    return UserProfile.Role.DRIVER


def _display_name_from_user(user: User) -> str:
    profile = getattr(user, "profile", None)
    if profile and profile.full_name:
        return profile.full_name
    return user.first_name or user.get_full_name() or user.username


def _serialize_user(user: User) -> dict:
    profile = getattr(user, "profile", None)
    role = _role_from_user(user)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": _display_name_from_user(user),
        "full_name": profile.full_name if profile else "",
        "phone": profile.phone if profile else "",
        "role": role,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "is_active": user.is_active,
        "can_access_dashboard": role == UserProfile.Role.ADMIN,
    }


def _serialize_event_detail(event: DrivingEvent, user: User) -> dict:
    is_admin = _is_admin_user(user)
    item = _serialize_event(event)
    item["permissions"] = {
        "can_review": bool(is_admin and event.review_status == DrivingEvent.ReviewStatus.PENDING),
        "can_appeal": bool((not is_admin) and event.review_status == DrivingEvent.ReviewStatus.AUTO),
    }
    return item


def _parse_bool_param(raw: str | None):
    value = str(raw or "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _gen_profile_id_card() -> str:
    stamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    return f"AUTO{stamp}{uuid.uuid4().hex[:10]}"[:32]


def _ensure_profile(user: User) -> UserProfile:
    profile = getattr(user, "profile", None)
    if profile:
        if not profile.id_card:
            profile.id_card = _gen_profile_id_card()
            profile.save(update_fields=["id_card"])
        return profile
    return UserProfile.objects.create(
        user=user,
        full_name=user.first_name or user.username,
        role=UserProfile.Role.ADMIN if user.is_staff else UserProfile.Role.DRIVER,
        phone="",
        id_card=_gen_profile_id_card(),
    )


def _apply_user_profile_mutation(user: User, payload: dict, *, is_create: bool = False):
    profile = _ensure_profile(user)

    full_name = str(payload.get("full_name") or payload.get("display_name") or "").strip()
    role = str(payload.get("role") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    id_card = str(payload.get("id_card") or "").strip()

    if full_name:
        profile.full_name = full_name[:64]
        user.first_name = full_name[:30]

    if role:
        if role not in {UserProfile.Role.ADMIN, UserProfile.Role.DRIVER}:
            raise ApiError(status=400, code=ERR_VALIDATION, message="invalid role")
        profile.role = role
        user.is_staff = role == UserProfile.Role.ADMIN

    if phone:
        profile.phone = phone[:20]

    if id_card:
        profile.id_card = id_card[:32]
    elif is_create and not profile.id_card:
        profile.id_card = _gen_profile_id_card()

    if "is_active" in payload:
        user.is_active = bool(payload.get("is_active"))

    user.save(update_fields=["first_name", "is_staff", "is_active"])
    profile.save()


def _handle_api(view):
    def _wrapped(request: HttpRequest, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except ApiError as exc:
            return _error(request, status=exc.status, code=exc.code, message=exc.message)
        except IntegrityError as exc:
            return _error(request, status=400, code=ERR_CONFLICT, message=f"integrity conflict: {exc}")
        except Exception:
            return _error(request, status=500, code=ERR_SERVER, message="internal server error")

    return _wrapped


@csrf_exempt
@require_http_methods(["POST"])
@_handle_api
def auth_login_v2(request: HttpRequest):
    payload = _parse_json(request)
    login_id = str(payload.get("username") or payload.get("login_id") or "").strip()
    password = str(payload.get("password") or "")
    if not login_id or not password:
        raise ApiError(status=400, code=ERR_VALIDATION, message="login_id and password required")

    username = resolve_username_from_login_id(login_id)
    user = authenticate(username=username, password=password)
    if user is None:
        raise ApiError(status=401, code=ERR_AUTH_REQUIRED, message="invalid credentials")

    auth_login(request, user)
    _ensure_profile(user)
    return _ok(request, {"session": {"user": _serialize_user(user)}})


@csrf_exempt
@require_http_methods(["POST"])
@_handle_api
def auth_register_v2(request: HttpRequest):
    payload = _parse_json(request)
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    full_name = str(payload.get("full_name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    id_card = str(payload.get("id_card") or "").strip()

    if not username or not password or not phone:
        raise ApiError(status=400, code=ERR_VALIDATION, message="username, password and phone are required")
    if len(password) < 6:
        raise ApiError(status=400, code=ERR_VALIDATION, message="password must be at least 6 characters")
    if User.objects.filter(username=username).exists():
        raise ApiError(status=409, code=ERR_CONFLICT, message="username already exists")
    if UserProfile.objects.filter(phone=phone).exists():
        raise ApiError(status=409, code=ERR_CONFLICT, message="phone already exists")

    with transaction.atomic():
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=full_name[:30],
            is_active=True,
            is_staff=False,
        )
        UserProfile.objects.create(
            user=user,
            full_name=full_name[:64],
            role=UserProfile.Role.DRIVER,
            phone=phone[:20],
            id_card=id_card[:32] or _gen_profile_id_card(),
        )

    auth_login(request, user)
    return _ok(request, {"session": {"user": _serialize_user(user)}}, message="registered")


@csrf_exempt
@require_http_methods(["POST"])
@_handle_api
def auth_logout_v2(request: HttpRequest):
    _require_auth(request)
    auth_logout(request)
    return _ok(request, {"logged_out": True})


@require_GET
@_handle_api
def auth_me_v2(request: HttpRequest):
    _require_auth(request)
    _ensure_profile(request.user)
    return _ok(request, {"session": {"user": _serialize_user(request.user)}})


@require_GET
@_handle_api
def dashboard_overview_v2(request: HttpRequest):
    _require_auth(request)
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

    return _ok(
        request,
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
                "false_positive_count": review_count.get(DrivingEvent.ReviewStatus.FALSE_POSITIVE, 0),
                "auto_count": review_count.get(DrivingEvent.ReviewStatus.AUTO, 0),
            },
            "trend": trend,
            "recent_events": recent_events,
            "meta": {
                "is_admin": _is_admin_user(request.user),
            },
        },
    )


@require_GET
@_handle_api
def events_list_v2(request: HttpRequest):
    _require_auth(request)
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

    return _ok(
        request,
        {
            "items": items,
            "summary": {
                "total": total,
                "total_duration_sec": round(float(stats.get("total_duration") or 0.0), 2),
                "avg_conf": round(float(stats.get("avg_conf") or 0.0), 3),
                "max_conf": round(float(stats.get("max_conf") or 0.0), 3),
                "pending_count": review_count.get(DrivingEvent.ReviewStatus.PENDING, 0),
                "confirmed_count": review_count.get(DrivingEvent.ReviewStatus.CONFIRMED, 0),
                "false_positive_count": review_count.get(DrivingEvent.ReviewStatus.FALSE_POSITIVE, 0),
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
        },
    )


@require_GET
@_handle_api
def event_detail_v2(request: HttpRequest, event_id: int):
    _require_auth(request)
    event = _events_base_queryset(request.user).filter(id=event_id).first()
    if event is None:
        raise ApiError(status=404, code=ERR_NOT_FOUND, message="event not found")
    return _ok(request, {"item": _serialize_event_detail(event, request.user)})


@csrf_exempt
@require_http_methods(["PATCH"])
@_handle_api
def event_review_v2(request: HttpRequest, event_id: int):
    _require_admin(request)
    payload = _parse_json(request)
    target_status = str(payload.get("review_status") or "").strip()
    note = str(payload.get("note") or "").strip()

    if target_status not in {DrivingEvent.ReviewStatus.CONFIRMED, DrivingEvent.ReviewStatus.FALSE_POSITIVE}:
        raise ApiError(status=400, code=ERR_VALIDATION, message="invalid review_status")

    event = _events_base_queryset(request.user).filter(id=event_id).first()
    if event is None:
        raise ApiError(status=404, code=ERR_NOT_FOUND, message="event not found")

    if event.review_status != DrivingEvent.ReviewStatus.PENDING:
        raise ApiError(status=409, code=ERR_CONFLICT, message="only pending events can be reviewed")

    event.review_status = target_status
    event.review_note = note[:255]
    event.reviewed_by = request.user
    event.reviewed_at = timezone.now()
    event.save(update_fields=["review_status", "review_note", "reviewed_by", "reviewed_at"])
    return _ok(request, {"item": _serialize_event_detail(event, request.user)}, message="review updated")


@csrf_exempt
@require_http_methods(["PATCH"])
@_handle_api
def event_appeal_v2(request: HttpRequest, event_id: int):
    _require_auth(request)
    if _is_admin_user(request.user):
        raise ApiError(status=403, code=ERR_PERMISSION_DENIED, message="admin cannot appeal")

    payload = _parse_json(request)
    note = str(payload.get("note") or "").strip()
    if not note:
        raise ApiError(status=400, code=ERR_VALIDATION, message="note is required")

    event = _events_base_queryset(request.user).filter(id=event_id).first()
    if event is None:
        raise ApiError(status=404, code=ERR_NOT_FOUND, message="event not found")

    if event.review_status != DrivingEvent.ReviewStatus.AUTO:
        raise ApiError(status=409, code=ERR_CONFLICT, message="only auto events can be appealed")

    event.review_status = DrivingEvent.ReviewStatus.PENDING
    event.review_note = note[:255]
    event.reviewed_by = None
    event.reviewed_at = None
    event.save(update_fields=["review_status", "review_note", "reviewed_by", "reviewed_at"])
    return _ok(request, {"item": _serialize_event_detail(event, request.user)}, message="appeal submitted")


def _admin_users_list_impl(request: HttpRequest):
    _require_admin(request)

    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip()
    is_active = _parse_bool_param(request.GET.get("is_active"))
    page = _safe_int(request.GET.get("page"), default=1, min_value=1)
    page_size = _safe_int(request.GET.get("page_size"), default=20, min_value=5, max_value=100)

    users = User.objects.select_related("profile").order_by("-date_joined")
    if q:
        users = users.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(profile__full_name__icontains=q)
            | Q(profile__phone__icontains=q)
        )

    if role in {UserProfile.Role.ADMIN, UserProfile.Role.DRIVER}:
        users = users.filter(profile__role=role)

    if is_active is not None:
        users = users.filter(is_active=is_active)

    paginator = Paginator(users, page_size)
    page_obj = paginator.get_page(page)

    items = []
    for user in page_obj.object_list:
        _ensure_profile(user)
        items.append(_serialize_user(user))

    return _ok(
        request,
        {
            "items": items,
            "pagination": {
                "page": page_obj.number,
                "page_size": page_size,
                "total": paginator.count,
                "total_pages": paginator.num_pages or 1,
            },
            "filters": {
                "q": q,
                "role": role,
                "is_active": is_active,
            },
        },
    )


def _admin_users_create_impl(request: HttpRequest):
    _require_admin(request)
    payload = _parse_json(request)

    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    if not username or not password:
        raise ApiError(status=400, code=ERR_VALIDATION, message="username and password are required")

    if User.objects.filter(username=username).exists():
        raise ApiError(status=409, code=ERR_CONFLICT, message="username already exists")

    role = str(payload.get("role") or UserProfile.Role.DRIVER).strip()
    if role not in {UserProfile.Role.ADMIN, UserProfile.Role.DRIVER}:
        raise ApiError(status=400, code=ERR_VALIDATION, message="invalid role")

    with transaction.atomic():
        user = User.objects.create(
            username=username,
            is_active=bool(payload.get("is_active", True)),
            is_staff=(role == UserProfile.Role.ADMIN),
        )
        user.set_password(password)
        user.save(update_fields=["password"])

        profile = UserProfile.objects.create(
            user=user,
            full_name=str(payload.get("full_name") or "").strip()[:64],
            role=role,
            phone=str(payload.get("phone") or "").strip()[:20],
            id_card=str(payload.get("id_card") or "").strip()[:32] or _gen_profile_id_card(),
        )
        if profile.full_name:
            user.first_name = profile.full_name[:30]
            user.save(update_fields=["first_name"])

    return _ok(request, {"item": _serialize_user(user)}, message="user created")


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_handle_api
def admin_users_list_v2(request: HttpRequest):
    if request.method == "POST":
        return _admin_users_create_impl(request)
    return _admin_users_list_impl(request)


@csrf_exempt
@require_http_methods(["PATCH"])
@_handle_api
def admin_users_update_v2(request: HttpRequest, user_id: int):
    _require_admin(request)
    payload = _parse_json(request)

    target = User.objects.select_related("profile").filter(id=user_id).first()
    if target is None:
        raise ApiError(status=404, code=ERR_NOT_FOUND, message="user not found")

    with transaction.atomic():
        _apply_user_profile_mutation(target, payload)

    return _ok(request, {"item": _serialize_user(target)}, message="user updated")
