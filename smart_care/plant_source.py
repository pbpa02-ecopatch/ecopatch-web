"""Where Smart Care learns which plants a user has.

TODO(smart_care): replace the body with a read of my_ecopatch.PatchPlant (status Planted or Growing)
and take the care intervals from Plant Library. Keep the signature `get_user_plants(user)` returning
a list of (plant_name, is_outdoor) so nothing else has to change.
"""
from .models import CareTask
from .suggestions import normalize


def get_user_plants(user):
    """Version 1: a plant exists once the user has made one task for it.

    Names are compared ignoring case and extra spaces, and the newest task decides the spelling and
    the indoor/outdoor flag, so one plant never shows up twice. Only the user's own tasks are read.
    """
    plants = {}
    rows = CareTask.objects.filter(user=user).order_by("-created_at", "-pk").values_list("plant_name", "is_outdoor")
    for plant_name, is_outdoor in rows:
        plants.setdefault(normalize(plant_name), (" ".join(plant_name.split()), is_outdoor))
    return sorted(plants.values(), key=lambda plant: normalize(plant[0]))
