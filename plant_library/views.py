from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PlantForm
from .models import Plant


def staff_required(view_func):
    """Decorator untuk membatasi akses view hanya bagi user staff/admin.

    Jika belum login, diarahkan ke halaman login.
    Jika login tapi bukan staff, dialihkan ke plant_list dengan notifikasi error.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url=settings.LOGIN_URL)
        if not request.user.is_staff:
            messages.error(request, 'Akses ditolak. Fitur ini hanya dapat diakses oleh Admin/Staff.')
            return redirect('plant_library:plant_list')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def plant_list(request):
    """Menampilkan daftar katalog tanaman dengan fitur pencarian dan filter."""
    plants = Plant.objects.all()

    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    sunlight = request.GET.get('sunlight', '').strip()
    difficulty = request.GET.get('difficulty', '').strip()
    indoor_outdoor = request.GET.get('indoor_outdoor', '').strip()
    space_requirement = request.GET.get('space_requirement', '').strip()

    if query:
        plants = plants.filter(name__icontains=query)
    if category:
        plants = plants.filter(category=category)
    if sunlight:
        plants = plants.filter(sunlight=sunlight)
    if difficulty:
        plants = plants.filter(difficulty=difficulty)
    if indoor_outdoor:
        plants = plants.filter(indoor_outdoor=indoor_outdoor)
    if space_requirement:
        plants = plants.filter(space_requirement=space_requirement)

    has_active_filters = bool(
        query or category or sunlight or difficulty or indoor_outdoor or space_requirement
    )

    context = {
        'plants': plants,
        'query': query,
        'selected_category': category,
        'selected_sunlight': sunlight,
        'selected_difficulty': difficulty,
        'selected_indoor_outdoor': indoor_outdoor,
        'selected_space_requirement': space_requirement,
        'has_active_filters': has_active_filters,
        'categories': Plant.Category.choices,
        'sunlight_choices': Plant.Sunlight.choices,
        'difficulty_choices': Plant.Difficulty.choices,
        'placement_choices': Plant.Placement.choices,
        'space_choices': Plant.SpaceRequirement.choices,
    }
    return render(request, 'plant_library/plant_list.html', context)


def plant_detail(request, pk):
    """Menampilkan rincian detail 1 tanaman."""
    plant = get_object_or_404(Plant, pk=pk)
    return render(request, 'plant_library/plant_detail.html', {'plant': plant})


@staff_required
def plant_create(request):
    """Menambahkan data tanaman baru (khusus Admin/Staff)."""
    if request.method == 'POST':
        form = PlantForm(request.POST)
        if form.is_valid():
            plant = form.save()
            messages.success(request, f'Tanaman "{plant.name}" berhasil ditambahkan ke katalog.')
            return redirect('plant_library:plant_detail', pk=plant.pk)
    else:
        form = PlantForm()

    context = {
        'form': form,
        'is_edit': False,
    }
    return render(request, 'plant_library/plant_form.html', context)


@staff_required
def plant_update(request, pk):
    """Mengubah data tanaman yang sudah ada (khusus Admin/Staff)."""
    plant = get_object_or_404(Plant, pk=pk)
    if request.method == 'POST':
        form = PlantForm(request.POST, instance=plant)
        if form.is_valid():
            plant = form.save()
            messages.success(request, f'Data tanaman "{plant.name}" berhasil diperbarui.')
            return redirect('plant_library:plant_detail', pk=plant.pk)
    else:
        form = PlantForm(instance=plant)

    context = {
        'form': form,
        'plant': plant,
        'is_edit': True,
    }
    return render(request, 'plant_library/plant_form.html', context)


@staff_required
def plant_delete(request, pk):
    """Menghapus data tanaman dengan proteksi ProtectedError (khusus Admin/Staff)."""
    plant = get_object_or_404(Plant, pk=pk)
    if request.method == 'POST':
        plant_name = plant.name
        try:
            plant.delete()
            messages.success(request, f'Tanaman "{plant_name}" berhasil dihapus dari katalog.')
            return redirect('plant_library:plant_list')
        except ProtectedError:
            messages.error(
                request,
                f'Tanaman "{plant_name}" tidak dapat dihapus karena masih digunakan pada EcoPatch pengguna atau modul lain.'
            )
            return redirect('plant_library:plant_detail', pk=plant.pk)

    return render(request, 'plant_library/plant_confirm_delete.html', {'plant': plant})
