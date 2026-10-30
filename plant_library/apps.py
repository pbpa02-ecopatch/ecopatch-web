from django.apps import AppConfig
from django.conf import settings
from django.core.management import call_command
from django.db.models.signals import post_migrate


def seed_initial_plants(sender=None, using='default', **kwargs):
    """Fill an empty library with the 60 starter plants (fixture initial_plants).

    Only when SEED_PLANTS_ON_MIGRATE is on, and only while the library has no plant at all, so it never
    duplicates or overwrites anything. It runs after every `migrate`, which a fresh deployment always does,
    so a server without a shell still ends up with data. Off by default: local work and tests are untouched.
    """
    if not settings.SEED_PLANTS_ON_MIGRATE:
        return
    from .models import Plant

    if Plant.objects.using(using).exists():
        return
    call_command('loaddata', 'initial_plants', database=using, verbosity=0)


class PlantLibraryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plant_library'

    def ready(self):
        post_migrate.connect(seed_initial_plants, sender=self, dispatch_uid='plant_library.seed_initial_plants')
