import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("my_ecopatch", "0004_patchplant_plant_alter_patchplant_plant_name"),
        ("smart_care", "0002_rework_caretask"),
    ]

    operations = [
        migrations.AddField(
            model_name="caretask",
            name="patch_plant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="care_tasks",
                to="my_ecopatch.patchplant",
            ),
        ),
    ]
