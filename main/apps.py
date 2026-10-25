from django.apps import AppConfig
from django.db.models.signals import post_migrate


def name_the_site(sender, **kwargs):
    """django.contrib.sites starts as "example.com"; allauth shows that name, so call it EcoPatch."""
    from django.conf import settings
    from django.contrib.sites.models import Site

    Site.objects.filter(pk=settings.SITE_ID, name='example.com').update(name='EcoPatch')


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

    def ready(self):
        post_migrate.connect(name_the_site, sender=self)
