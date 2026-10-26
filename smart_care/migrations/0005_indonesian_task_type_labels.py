from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("smart_care", "0004_link_existing_tasks"),
    ]

    operations = [
        # Only the labels of the choices changed (now Indonesian); the stored values and the column stay the same
        migrations.AlterField(
            model_name="caretask",
            name="task_type",
            field=models.CharField(
                choices=[
                    ("watering", "Penyiraman"),
                    ("fertilizing", "Pemupukan"),
                    ("pruning", "Pemangkasan"),
                    ("repotting", "Ganti pot"),
                    ("harvesting", "Panen"),
                    ("inspection", "Pemeriksaan"),
                ],
                max_length=20,
            ),
        ),
    ]
