from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import EcoPatchForm, PatchPlantForm
from .models import EcoPatch, PatchPlant

STATUS_ORDER = [
    PatchPlant.Status.GROWING,
    PatchPlant.Status.HARVESTED,
    PatchPlant.Status.PLANNED,
    PatchPlant.Status.PLANTED,
    PatchPlant.Status.REMOVED,
]


# ---------- helpers ----------

def _attach_status_summary(patches):
    """Tempelkan `plant_total` dan `status_summary` ke setiap EcoPatch.

    Satu query agregat untuk semua patch (bukan satu query per kartu).
    """
    counts = defaultdict(dict)
    rows = (
        PatchPlant.objects
        .filter(patch__in=patches)
        .values('patch_id', 'status')
        .annotate(total=Count('id'), quantity=Sum('quantity'))
    )
    quantities = defaultdict(int)
    for row in rows:
        quantities[row['patch_id']] += row['quantity']
        counts[row['patch_id']][row['status']] = row['total']

    for patch in patches:
        per_status = counts[patch.pk]
        patch.plant_total = sum(per_status.values())
        patch.plant_quantity = quantities[patch.pk]
        patch.status_summary = [
            {'key': status.value, 'label': status.label, 'count': per_status[status.value]}
            for status in STATUS_ORDER
            if per_status.get(status.value)
        ]
    return patches


def _get_patch(request, pk):
    """Ambil EcoPatch milik user yang login; milik orang lain -> 404."""
    return get_object_or_404(EcoPatch, pk=pk, owner=request.user)


def _is_htmx(request):
    return request.headers.get('HX-Request') == 'true'


def _detail_context(patch, plant_form=None, initial=None):
    _attach_status_summary([patch])
    return {
        'patch': patch,
        'plants': patch.plants.select_related('plant'),
        'plant_form': PatchPlantForm(initial=initial) if plant_form is None else plant_form,
        'status_choices': PatchPlant.Status.choices,
    }


def _plants_response(request, patch, plant_form=None, feedback=""):
    """htmx -> hanya panel tanaman (di-swap di halaman); non-htmx -> halaman detail penuh."""
    template = (
        'my_ecopatch/_plants_panel.html' if _is_htmx(request)
        else 'my_ecopatch/ecopatch_detail.html'
    )
    context = _detail_context(patch, plant_form)
    context["plant_feedback"] = feedback
    return render(request, template, context)


# ---------- EcoPatch: CRUD ----------

@login_required
def ecopatch_list(request):
    owned = EcoPatch.objects.filter(owner=request.user)
    query = request.GET.get('q', '').strip()
    space = request.GET.get('space', '')
    filtered = owned
    if query:
        filtered = filtered.filter(Q(name__icontains=query) | Q(city__icontains=query))
    if space in EcoPatch.SpaceType.values:
        filtered = filtered.filter(space_type=space)
    else:
        space = ''
    patches = list(filtered.prefetch_related('plants'))
    _attach_status_summary(patches)
    for patch in patches:
        patch.preview_plants = list(patch.plants.all())[:9]
    totals = PatchPlant.objects.filter(patch__owner=request.user).aggregate(
        plants=Sum('quantity'), growing=Sum('quantity', filter=Q(status=PatchPlant.Status.GROWING)),
    )
    return render(request, 'my_ecopatch/ecopatch_list.html', {
        'patches': patches, 'patch_count': owned.count(),
        'plant_count': totals['plants'] or 0, 'growing_count': totals['growing'] or 0,
        'query': query, 'selected_space': space, 'space_choices': EcoPatch.SpaceType.choices,
    })


@login_required
def ecopatch_detail(request, pk):
    patch = _get_patch(request, pk)
    # ?plant=<id> memilih tanaman di form tambah, supaya Plant Library bisa menautkan "Tambah ke EcoPatch".
    plant_id = request.GET.get('plant', '')
    initial = {'plant': plant_id} if plant_id.isdigit() else None
    return render(request, 'my_ecopatch/ecopatch_detail.html', _detail_context(patch, initial=initial))


@login_required
def ecopatch_create(request):
    if request.method == 'POST':
        form = EcoPatchForm(request.POST)
        if form.is_valid():
            patch = form.save(commit=False)
            patch.owner = request.user
            patch.save()
            messages.success(request, f'EcoPatch "{patch.name}" berhasil dibuat. Sekarang tambahkan tanamanmu.')
            return redirect('my_ecopatch:detail', pk=patch.pk)
    else:
        form = EcoPatchForm()
    return render(request, 'my_ecopatch/ecopatch_form.html', {'form': form, 'patch': None})


@login_required
def ecopatch_update(request, pk):
    patch = _get_patch(request, pk)
    if request.method == 'POST':
        form = EcoPatchForm(request.POST, instance=patch)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perubahan EcoPatch disimpan.')
            return redirect('my_ecopatch:detail', pk=patch.pk)
    else:
        form = EcoPatchForm(instance=patch)
    return render(request, 'my_ecopatch/ecopatch_form.html', {'form': form, 'patch': patch})


@login_required
@require_http_methods(['GET', 'POST'])
def ecopatch_delete(request, pk):
    patch = _get_patch(request, pk)
    if request.method == 'POST':
        name = patch.name
        patch.delete()
        messages.success(request, f'EcoPatch "{name}" dihapus.')
        return redirect('my_ecopatch:list')
    _attach_status_summary([patch])
    return render(request, 'my_ecopatch/ecopatch_confirm_delete.html', {'patch': patch})


# ---------- PatchPlant: tambah / ubah status / hapus (htmx, tetap jalan tanpa JS) ----------

@login_required
@require_POST
def patchplant_add(request, pk):
    patch = _get_patch(request, pk)
    form = PatchPlantForm(request.POST)
    feedback = ""
    if form.is_valid():
        plant = form.save(commit=False)
        plant.patch = patch
        plant.save()
        if not _is_htmx(request):
            messages.success(request, f'{plant.plant.name} ditambahkan ke {patch.name}.')
            return redirect('my_ecopatch:detail', pk=patch.pk)
        feedback = f"{plant.plant.name} berhasil ditambahkan."
        form = None  # form kosong baru untuk panel yang di-refresh
    return _plants_response(request, patch, form, feedback)


@login_required
@require_POST
def patchplant_set_status(request, pk):
    plant = get_object_or_404(PatchPlant.objects.select_related('patch'), pk=pk, patch__owner=request.user)
    new_status = request.POST.get('status')
    if new_status not in PatchPlant.Status.values:
        return HttpResponseBadRequest('Status tidak valid.')
    plant.status = new_status
    plant.save(update_fields=['status'])
    if not _is_htmx(request):
        return redirect('my_ecopatch:detail', pk=plant.patch_id)
    return _plants_response(request, plant.patch, feedback="Status tanaman berhasil disimpan.")


@login_required
@require_http_methods(["GET", "POST"])
def patchplant_delete(request, pk):
    plant = get_object_or_404(PatchPlant.objects.select_related('patch'), pk=pk, patch__owner=request.user)
    patch = plant.patch
    if request.method == "GET":
        return render(request, "my_ecopatch/plant_confirm_delete.html", {"plant": plant})
    plant.delete()
    if not _is_htmx(request):
        return redirect('my_ecopatch:detail', pk=patch.pk)
    return _plants_response(request, patch, feedback="Tanaman berhasil dihapus.")
