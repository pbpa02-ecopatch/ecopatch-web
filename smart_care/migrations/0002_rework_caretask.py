import django.utils.timezone
from django.db import migrations, models
from django.db.models import Q


def completed_flag_to_status(apps, schema_editor):
    CareTask = apps.get_model("smart_care", "CareTask")
    CareTask.objects.filter(is_completed=True).update(status="completed")


def status_to_completed_flag(apps, schema_editor):
    CareTask = apps.get_model("smart_care", "CareTask")
    CareTask.objects.filter(status="completed").update(is_completed=True)


class Migration(migrations.Migration):

    dependencies = [
        ("smart_care", "0001_initial"),
    ]

    operations = [
        # City now lives in the session / user profile, no longer on each task
        migrations.RemoveField(model_name="caretask", name="city"),
        migrations.AddField(
            model_name="caretask",
            name="plant_name",
            # existing rows get a neutral name; the default is not kept on the model
            field=models.CharField(default="Tanaman", max_length=80),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="caretask",
            name="is_outdoor",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="caretask",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="caretask",
            name="status",
            field=models.CharField(
                choices=[("pending", "Belum selesai"), ("completed", "Selesai"), ("skipped", "Dilewati")],
                default="pending",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="caretask",
            name="source",
            field=models.CharField(choices=[("manual", "Manual"), ("suggested", "Saran")], default="manual", max_length=10),
        ),
        # is_completed (bool) -> status, then the boolean goes away
        migrations.RunPython(completed_flag_to_status, status_to_completed_flag),
        migrations.RemoveField(model_name="caretask", name="is_completed"),
        migrations.AlterField(
            model_name="caretask",
            name="due_date",
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
        migrations.AlterModelOptions(
            name="caretask",
            options={"ordering": ["due_date", "created_at"]},
        ),
        migrations.AddConstraint(
            model_name="caretask",
            constraint=models.UniqueConstraint(
                condition=Q(source="suggested"),
                fields=("user", "plant_name", "task_type", "due_date"),
                name="smart_care_one_suggestion_per_day",
            ),
        ),
    ]
