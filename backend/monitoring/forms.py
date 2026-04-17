import re
import secrets

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import InviteCode, UserProfile


def resolve_username_from_login_id(login_id: str) -> str:
    value = (login_id or "").strip()
    if re.fullmatch(r"1\d{10}", value):
        profile = UserProfile.objects.select_related("user").filter(phone=value).first()
        if profile:
            return profile.user.username
    return value


class UidPhoneAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="账号", max_length=150)

    def clean(self):
        login_id = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if login_id is not None and password:
            username = resolve_username_from_login_id(login_id)
            self.cleaned_data["username"] = username
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class SignUpForm(UserCreationForm):
    username = forms.CharField(required=False, widget=forms.HiddenInput())
    full_name = forms.CharField(label="姓名", max_length=64, required=True)
    role = forms.ChoiceField(
        label="注册角色",
        choices=UserProfile.Role.choices,
        required=True,
        initial=UserProfile.Role.DRIVER,
    )
    gender = forms.ChoiceField(
        label="性别",
        choices=UserProfile.Gender.choices,
        required=True,
        initial=UserProfile.Gender.UNKNOWN,
    )
    phone = forms.CharField(label="手机号", max_length=20, required=True)
    invite_code = forms.CharField(
        label="管理员邀请码",
        max_length=32,
        required=False,
        help_text="仅管理员注册时需要。",
    )
    id_card = forms.CharField(
        label="身份证号",
        max_length=32,
        required=True,
        help_text="用于绑定个人数据，请填写真实身份证号。",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "full_name",
            "role",
            "gender",
            "phone",
            "invite_code",
            "id_card",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].required = False

    def _generate_uid(self):
        letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
        digits = "23456789"
        charset = letters + digits
        while True:
            # Ensure UID is exactly 6 chars and always mixed (letters + digits).
            uid_chars = [secrets.choice(letters), secrets.choice(digits)]
            uid_chars.extend(secrets.choice(charset) for _ in range(4))
            # Fisher-Yates shuffle with cryptographic randomness.
            for i in range(len(uid_chars) - 1, 0, -1):
                j = secrets.randbelow(i + 1)
                uid_chars[i], uid_chars[j] = uid_chars[j], uid_chars[i]
            uid = "".join(uid_chars)
            if not User.objects.filter(username=uid).exists():
                return uid

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            username = self._generate_uid()
        if not (
            len(username) == 6
            and all(c.isalnum() for c in username)
            and any(c.isalpha() for c in username)
            and any(c.isdigit() for c in username)
        ):
            raise forms.ValidationError("UID 格式必须是 6 位字母数字混合。")
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("UID 生成失败，请重试。")
        return username

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if not re.fullmatch(r"1\d{10}", phone):
            raise forms.ValidationError("手机号格式不正确，请输入 11 位手机号。")
        if UserProfile.objects.filter(phone=phone).exists():
            raise forms.ValidationError("该手机号已注册。")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        invite_code = (cleaned_data.get("invite_code") or "").strip().upper()
        self._invite_obj = None
        if role == UserProfile.Role.ADMIN:
            if not invite_code:
                self.add_error("invite_code", "管理员注册必须填写邀请码。")
                return cleaned_data
            invite_obj = InviteCode.objects.filter(
                code=invite_code, role=InviteCode.Role.ADMIN
            ).first()
            if not invite_obj:
                self.add_error("invite_code", "邀请码不存在。")
                return cleaned_data
            if not invite_obj.is_usable():
                if invite_obj.is_expired:
                    self.add_error("invite_code", "邀请码已过期。")
                else:
                    self.add_error("invite_code", "邀请码已失效或次数已用完。")
                return cleaned_data
            self._invite_obj = invite_obj
            cleaned_data["invite_code"] = invite_code
        return cleaned_data

    def clean_full_name(self):
        full_name = self.cleaned_data["full_name"].strip()
        if len(full_name) < 2:
            raise forms.ValidationError("姓名至少 2 个字符。")
        return full_name

    def clean_id_card(self):
        id_card = self.cleaned_data["id_card"].strip()
        if UserProfile.objects.filter(id_card=id_card).exists():
            raise forms.ValidationError("该身份证号已被注册。")
        return id_card

    def save(self, commit=True):
        user = super().save(commit=commit)
        user.first_name = self.cleaned_data["full_name"]
        role = self.cleaned_data["role"]
        if role == UserProfile.Role.ADMIN:
            user.is_staff = True
        user.save(update_fields=["first_name", "is_staff"])

        full_name = self.cleaned_data["full_name"]
        gender = self.cleaned_data["gender"] or UserProfile.Gender.UNKNOWN
        phone = self.cleaned_data["phone"]
        id_card = self.cleaned_data["id_card"]
        UserProfile.objects.create(
            user=user,
            full_name=full_name,
            role=role,
            gender=gender,
            phone=phone,
            id_card=id_card,
        )
        if role == UserProfile.Role.ADMIN and getattr(self, "_invite_obj", None):
            self._invite_obj.consume()
        return user
