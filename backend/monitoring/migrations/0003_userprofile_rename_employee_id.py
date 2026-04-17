import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0002_drivingevent_owner"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("id_card", models.CharField(max_length=32, unique=True, verbose_name="身份证号")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="账号",
                    ),
                ),
            ],
            options={
                "verbose_name": "用户资料",
                "verbose_name_plural": "用户资料",
            },
        ),
        migrations.RenameField(
            model_name="driver",
            old_name="employee_id",
            new_name="id_card",
        ),
        migrations.AlterField(
            model_name="drivingevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("risk", "危险驾驶"),
                    ("fatigue", "疲劳驾驶"),
                    ("distraction", "分心驾驶"),
                    ("unknown", "未知"),
                ],
                default="fatigue",
                max_length=32,
                verbose_name="事件类型",
            ),
        ),
        migrations.AlterModelOptions(
            name="drivingevent",
            options={
                "ordering": ["-start_time"],
                "verbose_name": "疲劳事件",
                "verbose_name_plural": "疲劳事件",
            },
        ),
    ]
