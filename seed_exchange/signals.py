from django.db.models.signals import post_save
from django.dispatch import receiver

from main.models import Profile

from .models import SeedExchange


@receiver(post_save, sender=Profile)
def copy_profile_to_listings(sender, instance, **kwargs):
    """Keep a member's listings in step with their profile.

    City and contact are only ever filled in on the profile; a listing carries a copy so it can be
    filtered by city. When the profile changes, the copy follows. An emptied field leaves the old copy.
    """
    changes = {}
    if instance.city:
        changes['city'] = instance.city
    contact = instance.contact_text()
    if contact:
        changes['contact'] = contact
    if changes:
        SeedExchange.objects.filter(user_id=instance.user_id).update(**changes)
