from django.db import migrations


def convert_legacy_pending_to_auto(apps, schema_editor):
    DrivingEvent = apps.get_model("monitoring", "DrivingEvent")
    DrivingEvent.objects.filter(
        review_status="pending",
        review_note="",
        reviewed_by__isnull=True,
        reviewed_at__isnull=True,
    ).update(review_status="auto")


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring", "0010_alter_drivingevent_review_status"),
    ]

    operations = [
        migrations.RunPython(
            convert_legacy_pending_to_auto, migrations.RunPython.noop
        ),
    ]
