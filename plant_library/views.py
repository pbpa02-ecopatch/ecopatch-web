from functools import wraps
from urllib.parse import urlencode
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render

from my_ecopatch.models import EcoPatch
from .forms import PlantForm
from .models import Plant


# ---------------------------------------------------------------------------
# Keyword mapping untuk pencarian natural language (tanpa AI/ML)
# Urutan dari frasa terpanjang ke terpendek agar tidak salah potong.
# ---------------------------------------------------------------------------
_KEYWORD_MAP = [
    # difficulty
    ("mudah dirawat",    "difficulty", "easy"),
    ("perawatan mudah",  "difficulty", "easy"),
    ("perawatan sedang", "difficulty", "medium"),
    # sunlight
    ("cahaya penuh",     "sunlight",   "full"),
    ("matahari penuh",   "sunlight",   "full"),
    # indoor / outdoor
    ("dalam ruangan",    "indoor_outdoor", "indoor"),
    ("luar ruangan",     "indoor_outdoor", "outdoor"),
    # shorter single-word phrases — must come after longer ones
    ("mudah",            "difficulty", "easy"),
    ("sedang",           "difficulty", "medium"),
    ("teduh",            "sunlight",   "shade"),
    ("indoor",           "indoor_outdoor", "indoor"),
    ("outdoor",          "indoor_outdoor", "outdoor"),
]

# Kata sambung / stop-word yang dibuang setelah frasa dipetakan
_STOP_WORDS = {"yang", "dan", "tanaman", "untuk", "dirawat"}

# Chip cepat di kotak pencarian. Sama seperti di landing page: tiga kelompok
# (cahaya, kesulitan, lokasi) supaya halaman ini terasa satu keluarga.
_CHIP_GROUPS = [
    ("sunlight", "Cahaya", "sun", [("full", "Cahaya penuh"), ("shade", "Teduh")]),
    ("difficulty", "Kesulitan", "care", [("easy", "Mudah dirawat"), ("medium", "Perawatan sedang")]),
    ("indoor_outdoor", "Lokasi", "place", [("indoor", "Indoor"), ("outdoor", "Outdoor")]),
]

_FILTER_FIELDS = ("q", "category", "sunlight", "difficulty", "indoor_outdoor", "space_requirement")


def _filter_params(request):
    """Filter yang sedang aktif, hanya dari parameter yang kita kenal."""
    return {key: request.GET.get(key, "").strip() for key in _FILTER_FIELDS if request.GET.get(key, "").strip()}


def build_chip_groups(params):
    """Bangun chip beserta href-nya, jadi template tidak perlu menyusun URL panjang.

    Klik chip yang sedang aktif akan mematikan filternya; klik chip lain akan
    mengganti nilai pada kelompok yang sama dan mempertahankan filter lain.
    """
    groups = []
    for field, label, tone, options in _CHIP_GROUPS:
        chips = []
        for value, text in options:
            active = params.get(field) == value
            next_params = {key: val for key, val in params.items() if key != field}
            if not active:
                next_params[field] = value
            chips.append({
                "label": text,
                "tone": tone,
                "active": active,
                "href": f"?{urlencode(next_params)}" if next_params else "?",
            })
        groups.append({"field": field, "label": label, "chips": chips})
    return groups


def matching_plants(patch):
    """Tanaman yang cocok dengan satu EcoPatch.

    Dipakai bersama oleh halaman Rekomendasi dan penanda "Cocok untuk kebunmu"
    di katalog, supaya keduanya tidak pernah berbeda aturan.
    """
    plants = Plant.objects.all()

    # Sinar matahari harus sama dengan kebun (kalau kebun mendefinisikannya).
    if patch.sunlight:
        plants = plants.filter(sunlight=patch.sunlight)

    # Ruang harus pas, atau tanaman memang bisa di mana saja.
    plants = plants.filter(space_requirement__in=[patch.space_type, 'any'])

    # Indoor hanya untuk tanaman indoor/both; sebaliknya untuk kebun luar.
    if patch.space_type == 'indoor':
        plants = plants.filter(indoor_outdoor__in=['indoor', 'both'])
    else:
        plants = plants.filter(indoor_outdoor__in=['outdoor', 'both'])

    return plants


def parse_query_keywords(raw_query):
    """Petakan kata kunci natural ke filter Django, kembalikan sisa teks.

    Returns:
        (filters_dict, remaining_text)
        - filters_dict: dict {field: value} yang berhasil dipetakan
        - remaining_text: teks yang tersisa setelah frasa & stop-word dibuang
    """
    text = re.sub(r'[^\w\s-]', ' ', raw_query.lower())
    text = re.sub(r'\s+', ' ', text).strip()
    filters = {}

    # Deteksi setiap frasa dari yang terpanjang; hapus dari teks setelah cocok
    for phrase, field, value in _KEYWORD_MAP:
        if phrase in text:
            # Satu kelompok hanya satu nilai: jangan timpa yang sudah ada
            if field not in filters:
                filters[field] = value
            text = text.replace(phrase, " ")

    # Buang stop-word
    words = text.split()
    remaining_words = [w for w in words if w not in _STOP_WORDS and w]
    remaining_text = " ".join(remaining_words).strip()

    return filters, remaining_text


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

    # Natural-language keyword parsing dari query teks
    kw_filters = {}
    if query:
        kw_filters, remaining_text = parse_query_keywords(query)

        # Terapkan filter dari kata kunci (jangan timpa filter eksplisit dari chip/select)
        if not sunlight and 'sunlight' in kw_filters:
            sunlight = kw_filters['sunlight']
        if not difficulty and 'difficulty' in kw_filters:
            difficulty = kw_filters['difficulty']
        if not indoor_outdoor and 'indoor_outdoor' in kw_filters:
            indoor_outdoor = kw_filters['indoor_outdoor']

        # Cari lewat nama/scientific_name hanya kalau masih ada sisa teks
        if remaining_text:
            plants = plants.filter(
                Q(name__icontains=remaining_text) |
                Q(scientific_name__icontains=remaining_text)
            )

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

    params = _filter_params(request)

    # Kalau filter datang dari kalimat pencarian, tampilkan apa yang kami baca
    # supaya orang tahu kenapa hasilnya menyempit.
    derived_labels = []
    label_maps = {
        'sunlight': dict(Plant.Sunlight.choices),
        'difficulty': dict(Plant.Difficulty.choices),
        'indoor_outdoor': dict(Plant.Placement.choices),
    }
    for field, value in kw_filters.items():
        if not request.GET.get(field):
            derived_labels.append(label_maps.get(field, {}).get(value, value))

    # Penanda "Cocok untuk kebunmu" hanya relevan kalau user punya EcoPatch.
    # Satu tanaman cukup cocok dengan salah satu kebun miliknya.
    match_ids = set()
    if request.user.is_authenticated:
        for patch in EcoPatch.objects.filter(owner=request.user):
            match_ids.update(matching_plants(patch).values_list('pk', flat=True))
    if match_ids:
        plants = list(plants)
        for plant in plants:
            plant.is_match = plant.pk in match_ids

    context = {
        'plants': plants,
        'query': query,
        'selected_category': category,
        'selected_sunlight': sunlight,
        'selected_difficulty': difficulty,
        'selected_indoor_outdoor': indoor_outdoor,
        'selected_space_requirement': space_requirement,
        'has_active_filters': has_active_filters,
        'filter_groups': build_chip_groups(params),
        'derived_labels': derived_labels,
        'active_params': params,
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

    # Kebun mana saja yang cocok dengan tanaman ini. Detail memakai nama
    # kebunnya supaya user tahu harus menanamnya di mana.
    matching_patches = []
    if request.user.is_authenticated:
        for patch in EcoPatch.objects.filter(owner=request.user):
            if matching_plants(patch).filter(pk=plant.pk).exists():
                matching_patches.append(patch)

    return render(request, 'plant_library/plant_detail.html', {
        'plant': plant,
        'matching_patches': matching_patches,
    })


@login_required
def plant_recommend(request):
    """Memberikan rekomendasi tanaman berdasarkan kondisi EcoPatch milik user."""
    # Label EcoPatch masih berbahasa Inggris; halaman ini memakai istilah Indonesia
    # supaya seragam dengan kartu tanaman di bawahnya.
    space_labels = {
        'balcony': 'Balkon',
        'indoor': 'Dalam ruangan',
        'terrace': 'Teras',
        'rooftop': 'Atap',
        'small_yard': 'Halaman kecil',
    }
    sun_labels = {
        'full': 'Cahaya penuh',
        'partial': 'Cahaya sedang',
        'shade': 'Teduh',
    }

    user_patches = EcoPatch.objects.filter(owner=request.user)

    if not user_patches.exists():
        return render(request, 'plant_library/plant_recommend.html', {
            'user_patches': user_patches,
            'selected_patch': None,
            'recommended_plants': [],
            'match_reason': '',
        })

    patch_id = request.GET.get('patch')
    selected_patch = None
    if patch_id:
        selected_patch = user_patches.filter(pk=patch_id).first()

    if not selected_patch:
        selected_patch = user_patches.first()

    # Logika filter rekomendasi murni Django (tanpa ML/AI)
    recommended_plants = matching_plants(selected_patch)

    # Format alasan kecocokan
    space_label = space_labels.get(selected_patch.space_type, selected_patch.get_space_type_display())
    sunlight_label = sun_labels.get(selected_patch.sunlight, 'segala intensitas sinar')
    match_reason = f"Cocok untuk area {space_label.lower()} dengan kebutuhan sinar {sunlight_label.lower()}."

    patch_options = [
        {
            'pk': patch.pk,
            'name': patch.name,
            'space_label': space_labels.get(patch.space_type, patch.get_space_type_display()),
            'sun_label': sun_labels.get(patch.sunlight) if patch.sunlight else '',
        }
        for patch in user_patches
    ]

    context = {
        'user_patches': user_patches,
        'patch_options': patch_options,
        'selected_patch': selected_patch,
        'selected_space_label': space_labels.get(selected_patch.space_type, selected_patch.get_space_type_display()),
        'selected_sun_label': sun_labels.get(selected_patch.sunlight, 'Segala sinar') if selected_patch.sunlight else 'Segala sinar',
        'recommended_plants': recommended_plants,
        'match_reason': match_reason,
    }
    return render(request, 'plant_library/plant_recommend.html', context)


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
