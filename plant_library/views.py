from functools import wraps
import json
from urllib.parse import urlencode
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers

from my_ecopatch.models import EcoPatch, PatchPlant
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
    # watering
    ("tahan lupa disiram", "watering", "low"),
    ("jarang disiram",     "watering", "low"),
    ("sering disiram",     "watering", "high"),
    ("siram sedang",       "watering", "moderate"),
    ("penyiraman sedang",  "watering", "moderate"),
    ("jarang siram",       "watering", "low"),
    ("sering siram",       "watering", "high"),
    # shorter single-word phrases — must come after longer ones
    ("mudah",            "difficulty", "easy"),
    ("sedang",           "difficulty", "medium"),
    ("teduh",            "sunlight",   "shade"),
    ("indoor",           "indoor_outdoor", "indoor"),
    ("outdoor",          "indoor_outdoor", "outdoor"),
]

# Kata sambung / stop-word yang dibuang setelah frasa dipetakan
# Kata tanya ("tanaman apa yang cocok di ...?") ikut dibuang, supaya kalimat dari saran di landing page
# hanya meninggalkan filter, bukan kata yang dikira nama tanaman.
_STOP_WORDS = {
    "yang", "dan", "tanaman", "untuk", "dirawat",
    "apa", "apakah", "di", "ke", "dari", "dengan", "cocok", "ada", "ya", "dong", "sebaiknya", "paling",
    "disiram", "siram", "penyiraman",
}

# Chip cepat di kotak pencarian. Sama seperti di landing page: tiga kelompok
# (cahaya, kesulitan, lokasi) supaya halaman ini terasa satu keluarga.
_CHIP_GROUPS = [
    ("sunlight", "Cahaya", "sun", [("full", "Cahaya penuh"), ("shade", "Teduh")]),
    ("difficulty", "Kesulitan", "care", [("easy", "Mudah dirawat"), ("medium", "Perawatan sedang")]),
    ("indoor_outdoor", "Lokasi", "place", [("indoor", "Indoor"), ("outdoor", "Outdoor")]),
]

_FILTER_FIELDS = ("q", "category", "sunlight", "difficulty", "indoor_outdoor", "space_requirement", "watering")


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


def _filter_url(params, name, value):
    """URL daftar dengan satu filter diganti, filter lain tetap terbawa."""
    current = {key: val for key, val in params.items() if val}
    if value:
        current[name] = value
    else:
        current.pop(name, None)
    query_string = urlencode(current)
    base = reverse('plant_library:plant_list')
    return f'{base}?{query_string}' if query_string else base


def _filter_dropdowns(params):
    """Dropdown filter gaya Seed Exchange: label aktif + daftar tautan."""
    config = [
        ('category', 'Semua kategori', Plant.Category.choices),
        ('watering', 'Semua penyiraman', Plant.Watering.choices),
        ('space_requirement', 'Semua ruang', Plant.SpaceRequirement.choices),
    ]
    dropdowns = []
    for name, all_label, options in config:
        labels = dict(options)
        current_value = params.get(name, '')
        items = [{
            'label': all_label,
            'url': _filter_url(params, name, ''),
            'selected': not current_value,
        }]
        for value, label in options:
            items.append({
                'label': label,
                'url': _filter_url(params, name, value),
                'selected': current_value == value,
            })
        dropdowns.append({
            'name': name,
            'current_label': labels.get(current_value, all_label),
            'items': items,
            'is_active': bool(current_value),
        })
    return dropdowns


# How a patch's space is called next to a plant: the same words the Plant Library uses for "ruang".
_SPACE_LABELS = {
    'indoor': 'Indoor', 'balcony': 'Balkon', 'terrace': 'Teras', 'rooftop': 'Atap', 'small_yard': 'Halaman kecil',
}


def fit_hint(plant, patch):
    """A short, honest line about putting this plant in this EcoPatch: (tone, text).

    Tones: "ok" fits, "tip" fits if placed well, "warn" is a poor fit, "muted" is already there.
    """
    if plant.space_requirement not in ('any', patch.space_type):
        return 'warn', f'Butuh ruang {plant.get_space_requirement_display().lower()}'
    if patch.sunlight and plant.sunlight != patch.sunlight:
        needs = {'full': 'Butuh cahaya penuh', 'partial': 'Butuh cahaya sedang', 'shade': 'Lebih suka tempat teduh'}
        return 'warn', needs.get(plant.sunlight, 'Cahaya kurang pas')
    if plant.sunlight == 'full' and patch.space_type == 'indoor':
        return 'tip', 'Taruh dekat jendela yang terang'
    if plant.sunlight == 'shade' and patch.space_type != 'indoor':
        return 'tip', 'Taruh di sudut yang teduh'
    return 'ok', 'Cocok'


def attach_patch_options(plants, user):
    """Give every plant card the member's EcoPatches to add it to (one query for patches, one for what is in them)."""
    patches = list(EcoPatch.objects.filter(owner=user).order_by('name'))
    held = set(
        PatchPlant.objects.filter(patch__in=patches).exclude(status=PatchPlant.Status.REMOVED)
        .values_list('patch_id', 'plant_id')
    )
    for plant in plants:
        options = []
        for patch in patches:
            if (patch.pk, plant.pk) in held:
                tone, text = 'muted', 'Sudah ada di sini'
            else:
                tone, text = fit_hint(plant, patch)
            place = _SPACE_LABELS.get(patch.space_type, patch.get_space_type_display())
            options.append({'patch': patch, 'place': f'{place} \u00b7 {patch.city}' if patch.city else place, 'tone': tone, 'hint': text})
        plant.patch_options = options
        plant.can_add = True
    return plants


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
    watering = request.GET.get('watering', '').strip()
    if watering not in dict(Plant.Watering.choices):
        watering = ''

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
        if not watering and 'watering' in kw_filters:
            watering = kw_filters['watering']

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
    if watering:
        plants = plants.filter(watering=watering)

    has_active_filters = bool(
        query or category or sunlight or difficulty or indoor_outdoor or space_requirement or watering
    )

    params = _filter_params(request)

    # Kalau filter datang dari kalimat pencarian, tampilkan apa yang kami baca
    # supaya orang tahu kenapa hasilnya menyempit.
    derived_labels = []
    label_maps = {
        'sunlight': dict(Plant.Sunlight.choices),
        'difficulty': dict(Plant.Difficulty.choices),
        'indoor_outdoor': dict(Plant.Placement.choices),
        'watering': dict(Plant.Watering.choices),
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
    if request.user.is_authenticated:
        plants = attach_patch_options(list(plants), request.user)

    context = {
        'plants': plants,
        'query': query,
        'selected_category': category,
        'selected_sunlight': sunlight,
        'selected_difficulty': difficulty,
        'selected_indoor_outdoor': indoor_outdoor,
        'selected_space_requirement': space_requirement,
        'selected_watering': watering,
        'has_active_filters': has_active_filters,
        'filter_groups': build_chip_groups(params),
        'dropdowns': _filter_dropdowns(params),
        'derived_labels': derived_labels,
        'active_params': params,
        'categories': Plant.Category.choices,
        'sunlight_choices': Plant.Sunlight.choices,
        'difficulty_choices': Plant.Difficulty.choices,
        'placement_choices': Plant.Placement.choices,
        'space_choices': Plant.SpaceRequirement.choices,
        'watering_choices': Plant.Watering.choices,
        'plant_names_json': json.dumps(list(Plant.objects.values_list('name', flat=True).distinct().order_by('name'))),
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

    # Anyone logged in can add the plant to one of their EcoPatches from the sheet (the same list the card's + opens).
    if request.user.is_authenticated:
        attach_patch_options([plant], request.user)

    context = {'plant': plant, 'matching_patches': matching_patches}
    # A card opens the same sheet in a pop-up: that asks for only the sheet (and the link still works as a page).
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        context['in_modal'] = True
        response = render(request, 'plant_library/partials/detail_body.html', context)
    else:
        response = render(request, 'plant_library/plant_detail.html', context)
    patch_vary_headers(response, ['X-Requested-With'])
    return response


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
    if patch_id and patch_id.isdecimal() and len(patch_id) <= 19:
        selected_patch = user_patches.filter(pk=patch_id).first()

    if not selected_patch:
        selected_patch = user_patches.first()

    # Logika filter rekomendasi murni Django (tanpa ML/AI)
    recommended_plants = attach_patch_options(list(matching_plants(selected_patch)), request.user)

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
