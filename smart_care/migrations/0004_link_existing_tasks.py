from django.db import migrations


def _normalize(name):
    # same rule as smart_care.suggestions.normalize, copied so the migration does not depend on app code
    return " ".join(name.split()).casefold()


def link_tasks_to_plants(apps, schema_editor):
    """Link tasks made from a typed plant name to the user's plant in My EcoPatch with that name.

    Only an unambiguous match is linked: exactly one plant of that user has the name. If the user has two plants
    with the same name (or none), the task is left without a link and keeps its plant_name as it was.
    """
    CareTask = apps.get_model("smart_care", "CareTask")
    PatchPlant = apps.get_model("my_ecopatch", "PatchPlant")

    owned = {}
    for patch_plant in PatchPlant.objects.select_related("plant", "patch"):
        name = patch_plant.plant.name if patch_plant.plant_id else patch_plant.plant_name
        owned.setdefault((patch_plant.patch.owner_id, _normalize(name)), []).append(patch_plant.pk)

    for task in CareTask.objects.filter(patch_plant__isnull=True).only("pk", "user_id", "plant_name"):
        matches = owned.get((task.user_id, _normalize(task.plant_name)), [])
        if len(matches) == 1:
            CareTask.objects.filter(pk=task.pk).update(patch_plant_id=matches[0])


class Migration(migrations.Migration):

    dependencies = [
        ("my_ecopatch", "0004_patchplant_plant_alter_patchplant_plant_name"),
        ("smart_care", "0003_caretask_patch_plant"),
    ]

    operations = [
        # Nothing to undo: a link only adds information, and plant_name was never changed. Going back past
        # 0003 drops the column anyway; going back to 0003 keeps the links, and running this again is harmless.
        migrations.RunPython(link_tasks_to_plants, migrations.RunPython.noop),
    ]
