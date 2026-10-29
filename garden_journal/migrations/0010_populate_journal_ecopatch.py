from django.db import migrations


def populate_ecopatch_fk(apps, schema_editor):
    GardenJournal = apps.get_model("garden_journal", "GardenJournal")
    EcoPatch = apps.get_model("my_ecopatch", "EcoPatch")

    # Match each journal's ecopatch_name with an EcoPatch owned by the same user
    for journal in GardenJournal.objects.filter(ecopatch__isnull=True).exclude(ecopatch_name=""):
        if journal.user_id and journal.ecopatch_name:
            patch = EcoPatch.objects.filter(
                owner_id=journal.user_id,
                name__iexact=journal.ecopatch_name.strip(),
            ).first()
            if patch:
                journal.ecopatch = patch
                journal.save(update_fields=["ecopatch"])


def reverse_populate(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("my_ecopatch", "0001_initial"),
        ("garden_journal", "0009_gardenjournal_ecopatch"),
    ]

    operations = [
        migrations.RunPython(populate_ecopatch_fk, reverse_code=reverse_populate),
    ]
