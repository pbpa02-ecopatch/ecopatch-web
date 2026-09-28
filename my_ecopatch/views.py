from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from .models import EcoPatch, PatchPlant

STATUS_ORDER = [
    PatchPlant.Status.GROWING,
    PatchPlant.Status.HARVESTED,
    PatchPlant.Status.PLANNED,
    PatchPlant.Status.PLANTED,
    PatchPlant.Status.REMOVED,
]


def _attach_status_summary(patches):
    """Tempelkan `plant_total` dan `status_summary` ke setiap EcoPatch.

    Satu query agregat untuk semua patch (bukan satu query per kartu).
    """
    counts = defaultdict(dict)
    rows = (
        PatchPlant.objects
        .filter(patch__in=patches)
        .values('patch_id', 'status')
        .annotate(total=Count('id'))
    )
    for row in rows:
        counts[row['patch_id']][row['status']] = row['total']

    for patch in patches:
        per_status = counts[patch.pk]
        patch.plant_total = sum(per_status.values())
        patch.status_summary = [
            {'key': status.value, 'label': status.label, 'count': per_status[status.value]}
            for status in STATUS_ORDER
            if per_status.get(status.value)
        ]
    return patches


@login_required
def ecopatch_list(request):
    patches = list(EcoPatch.objects.filter(owner=request.user))
    _attach_status_summary(patches)
    return render(request, 'my_ecopatch/ecopatch_list.html', {'patches': patches})
