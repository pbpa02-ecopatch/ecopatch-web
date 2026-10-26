"""Where Smart Care learns which plants a user has: the plants in the user's My EcoPatch.

A plant takes part in care (task form, suggestions, pots) while its status in My EcoPatch is Planted or
Growing. A task links to its plant, but copies the plant's name and the indoor/outdoor flag when it is linked,
so the history still reads right after the plant is renamed or removed.
"""
from django.db.models import Q

from my_ecopatch.models import EcoPatch, PatchPlant

from plant_library.models import Plant

from .suggestions import INTERVALS, normalize

CARE_STATUSES = (PatchPlant.Status.PLANTED, PatchPlant.Status.GROWING)
NAME_MAX_LENGTH = 80  # CareTask.plant_name


def patch_plant_name(patch_plant):
    """The Plant Library name, or the old free-text name of a row not linked to the library yet."""
    name = patch_plant.plant.name if patch_plant.plant_id else patch_plant.plant_name
    return " ".join(name.split())[:NAME_MAX_LENGTH]


def is_outdoor(patch_plant):
    """Whether the rain advice applies. An indoor EcoPatch keeps its plants out of it, and so does a Plant
    Library plant that is labelled indoor, wherever it was put; outdoor and both follow the EcoPatch."""
    if patch_plant.patch.space_type == EcoPatch.SpaceType.INDOOR:
        return False
    return not (patch_plant.plant_id and patch_plant.plant.indoor_outdoor == Plant.Placement.INDOOR)


def watering_days(patch_plant):
    """Days between two waterings of this plant: the Plant Library estimate, or the default for an old row
    that is not linked to the library yet."""
    if patch_plant.plant_id:
        return patch_plant.plant.watering_interval_days
    return INTERVALS["watering"]


def link_task(task, patch_plant):
    """Point a task at a plant and snapshot the plant's name and indoor/outdoor flag onto it."""
    task.patch_plant = patch_plant
    task.plant_name = patch_plant_name(patch_plant)
    task.is_outdoor = is_outdoor(patch_plant)


def user_patch_plants(user, keep=None):
    """The user's own plants that can have care tasks. `keep` is a plant that stays listed even when its
    status no longer qualifies (the plant of a task being edited). Other users' plants never appear."""
    wanted = Q(status__in=CARE_STATUSES)
    if keep is not None:
        wanted |= Q(pk=keep)
    return (
        PatchPlant.objects.filter(patch__owner=user)
        .filter(wanted)
        .select_related("plant", "patch")
        .order_by("patch__name", "plant__name", "plant_name", "pk")
    )


def _one_per_name(user):
    """One plant per name (ignoring case and extra spaces): the newest My EcoPatch row decides the spelling and
    the indoor/outdoor flag, so a plant that sits in two patches is still one pot."""
    chosen = {}
    for patch_plant in user_patch_plants(user).order_by("-pk"):
        name = patch_plant_name(patch_plant)
        if name:
            chosen.setdefault(normalize(name), patch_plant)
    return sorted(chosen.values(), key=lambda patch_plant: normalize(patch_plant_name(patch_plant)))


def get_user_plants(user):
    """[(plant_name, is_outdoor)] sorted by name; this is what the suggestions and the pots are built from."""
    return [(patch_plant_name(patch_plant), is_outdoor(patch_plant)) for patch_plant in _one_per_name(user)]


def get_user_watering_days(user):
    """{normalized plant name: days between waterings} for the same plants get_user_plants returns."""
    return {normalize(patch_plant_name(patch_plant)): watering_days(patch_plant) for patch_plant in _one_per_name(user)}


def find_patch_plant(user, name):
    """The user's plant behind a plant name posted by the suggestion buttons, or None."""
    wanted = normalize(name)
    for patch_plant in _one_per_name(user):
        if normalize(patch_plant_name(patch_plant)) == wanted:
            return patch_plant
    return None


def get_user_city(user):
    """City of the user's newest EcoPatch that has a plant needing care, or '' when there is none."""
    city = (
        EcoPatch.objects.filter(owner=user, plants__status__in=CARE_STATUSES)
        .order_by("-created_at", "-pk")
        .values_list("city", flat=True)
        .first()
    )
    return city or ""
