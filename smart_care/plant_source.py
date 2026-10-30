"""Where Smart Care learns which plants a user has: the plants in the user's My EcoPatch.

A plant takes part in care (task form, suggestions, pots) while its status in My EcoPatch is Planted or
Growing. Every row is its own pot: the same plant kept in two places (say indoors and on the balcony) has its own
history, suggestions and indoor/outdoor flag. A task links to its plant, but copies the plant's name and the indoor/outdoor flag when it is linked,
so the history still reads right after the plant is renamed in the Plant Library (removing the plant deletes its tasks).
"""
from collections import Counter

from django.db.models import Q

from my_ecopatch.models import EcoPatch, PatchPlant

from plant_library.models import Plant

from .suggestions import INTERVALS, normalize

# Alur data tanaman:
#   EcoPatch (kebun user) -> PatchPlant (tanaman di kebun itu) -> Plant (Plant Library)
# PatchPlant memberi status dan kebun, Plant memberi nama resmi, label indoor/outdoor, dan interval siram.
# Semua fungsi publik di bawah menerima `user` dan hanya membaca tanaman milik user itu (lewat patch__owner),
# sehingga saran, pot, dan dropdown form tidak pernah memuat tanaman user lain.
# Hanya tanaman berstatus Planted atau Growing yang ikut dirawat; bibit yang belum ditanam atau yang sudah dipanen tidak.
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
    # Q objects digabung dengan OR: status aktif ATAU tanaman milik task yang sedang diedit.
    wanted = Q(status__in=CARE_STATUSES)
    if keep is not None:
        wanted |= Q(pk=keep)
    # select_related mengambil plant dan patch dalam satu query. Tanpa itu, membaca nama dan flag outdoor
    # tiap tanaman memicu query tambahan (masalah N+1).
    return (
        PatchPlant.objects.filter(patch__owner=user)
        .filter(wanted)
        .select_related("plant", "patch")
        .order_by("patch__name", "plant__name", "plant_name", "pk")
    )


def get_user_plants(user):
    """[(plant_name, is_outdoor, patch_plant_id, place)] with one entry per plant row, sorted by name.

    Each row is a pot of its own, because the same plant in two places is cared for differently (its own history, its
    own flag). `patch_plant_id` is what the page and the suggestion buttons use to point at one pot. `place` is the
    EcoPatch name, filled in only when the same plant name occurs more than once, so the page can tell them apart.
    """
    rows = [(patch_plant_name(patch_plant), patch_plant) for patch_plant in user_patch_plants(user)]
    rows = [(name, patch_plant) for name, patch_plant in rows if name]  # a plant without any name cannot be shown
    counts = Counter(normalize(name) for name, _ in rows)
    pots = [
        (name, is_outdoor(patch_plant), patch_plant.pk, patch_plant.patch.name if counts[normalize(name)] > 1 else "")
        for name, patch_plant in rows
    ]
    return sorted(pots, key=lambda pot: (normalize(pot[0]), pot[3].casefold(), pot[2]))


def get_user_watering_days(user):
    """{patch_plant_id: days between waterings} for the same plants get_user_plants returns."""
    return {
        patch_plant.pk: watering_days(patch_plant)
        for patch_plant in user_patch_plants(user)
        if patch_plant_name(patch_plant)
    }


def find_patch_plant(user, patch_plant_id):
    """The user's plant row behind an id posted by the suggestion buttons, or None. The id comes from the browser,
    so it is only trusted when it is a number and the row is one of this user's plants that take part in care."""
    try:
        wanted = int(patch_plant_id)
    except (TypeError, ValueError):
        return None
    patch_plant = user_patch_plants(user).filter(pk=wanted).first()
    return patch_plant if patch_plant and patch_plant_name(patch_plant) else None


def get_user_city(user):
    """City of the user's newest EcoPatch that has a plant needing care, or '' when there is none."""
    city = (
        EcoPatch.objects.filter(owner=user, plants__status__in=CARE_STATUSES)
        .order_by("-created_at", "-pk")
        .values_list("city", flat=True)
        .first()
    )
    return city or ""
