# TAHAP B (opsional): salin baris lama (plant_name) ke FK plant.
# Hanya perlu kalau database-mu punya PatchPlant yang ingin dipertahankan.
#
#   python manage.py makemigrations my_ecopatch --empty -n link_patchplant_to_plant
#
# Lalu ganti isi file migrasi kosong yang dibuat dengan kode di bawah, tapi PERTAHANKAN
# baris `dependencies` yang dibuat Django (tambahkan juga ('plant_library', '0001_initial') bila belum ada).

from django.db import migrations


def link_plants(apps, schema_editor):
    PatchPlant = apps.get_model('my_ecopatch', 'PatchPlant')
    Plant = apps.get_model('plant_library', 'Plant')
    for row in PatchPlant.objects.filter(plant__isnull=True).exclude(plant_name=''):
        match = Plant.objects.filter(name__iexact=row.plant_name.strip()).first()
        if match:
            row.plant = match
            row.save(update_fields=['plant'])


class Migration(migrations.Migration):

    dependencies = [
        # ('my_ecopatch', '0003_...'),        <- biarkan yang dibuat Django
        ('plant_library', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(link_plants, migrations.RunPython.noop),
    ]
