import datetime
from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import GardenJournalForm
from .models import GardenJournal


def _filter_date(value):
    """Ignore malformed query dates before they reach ORM date conversion."""
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _journal_filter_url(active, **changes):
    """Build a list URL, keeping every other active filter intact."""
    params = {key: value for key, value in active.items() if value}
    for key, value in changes.items():
        if value:
            params[key] = value
        else:
            params.pop(key, None)
    query = urlencode(params)
    base = reverse("garden_journal:list")
    return f"{base}?{query}" if query else base


def _journal_filter_dropdowns(active, ecopatch_names, conditions, show_photo_filter=False):
    """Dropdown options in the same shape the Seed Exchange filter uses.

    ``show_photo_filter`` should be True only when at least one journal entry
    already has a photo attached (i.e. the upload feature is live).  Pass False
    (the default) to hide the photo filter entirely while the feature is still
    being built.
    """
    config = [
        ("ecopatch_name", "Semua EcoPatch", [(name, name) for name in ecopatch_names]),
        ("condition", "Semua Kondisi", list(conditions)),
        # Photo filter — hidden until upload feature is live.
        # When show_photo_filter=True this entry is included with updated labels:
        #   all  → "Semua Catatan"
        #   yes  → "Ada Foto"
        #   no   → "Tanpa Foto"
        *([("has_photo", "Semua Catatan", [("yes", "Ada Foto"), ("no", "Tanpa Foto")])]
          if show_photo_filter else []),
        ("sort", "Urutkan", [
            ("newest", "Terbaru"),
            ("oldest", "Terlama"),
            ("a_z", "A → Z"),
            ("z_a", "Z → A"),
        ]),
    ]
    dropdowns = []
    for name, all_label, options in config:
        labels = dict(options)
        current = active.get(name, "")
        items = [
            {
                "label": all_label,
                "url": _journal_filter_url(active, **{name: ""}),
                "selected": not current,
            }
        ]
        for value, label in options:
            items.append(
                {
                    "label": label,
                    "url": _journal_filter_url(active, **{name: value}),
                    "selected": current == value,
                }
            )
        dropdowns.append(
            {
                "name": name,
                "current_label": labels.get(current, all_label),
                "items": items,
                "is_active": bool(current),
                "aria_label": "Filter foto" if name == "has_photo" else ("Filter " + all_label.replace("Semua ", "") if all_label.startswith("Semua ") else all_label),
            }
        )
    return dropdowns


def _get_filtered_journals(request):
    """Helper query filter untuk list dan AJAX live filter."""
    journals = GardenJournal.objects.filter(user=request.user).select_related("ecopatch")

    ecopatch_param = request.GET.get("ecopatch", "").strip() or request.GET.get("ecopatch_name", "").strip()
    plant_name = request.GET.get("plant_name", "").strip()
    condition = request.GET.get("condition", "").strip()
    date_from = _filter_date(request.GET.get("date_from", "").strip())
    date_to = _filter_date(request.GET.get("date_to", "").strip())

    if ecopatch_param:
        if ecopatch_param.isdecimal():
            if len(ecopatch_param) > 19:
                return journals.none()
            journals = journals.filter(ecopatch_id=int(ecopatch_param))
        else:
            journals = journals.filter(
                Q(ecopatch__name__icontains=ecopatch_param) | Q(ecopatch_name__icontains=ecopatch_param)
            )
    if plant_name:
        journals = journals.filter(plant_name__icontains=plant_name)
    if condition:
        journals = journals.filter(plant_condition=condition)
    if date_from:
        journals = journals.filter(date__gte=date_from)
    if date_to:
        journals = journals.filter(date__lte=date_to)

    has_photo = request.GET.get("has_photo", "").strip()
    if has_photo == "yes":
        # Ada Foto: hanya catatan yang punya foto
        journals = journals.exclude(image="").exclude(image__isnull=True)
    elif has_photo == "no":
        # Tanpa Foto: hanya catatan tanpa foto
        journals = journals.filter(Q(image="") | Q(image__isnull=True))

    sort = request.GET.get("sort", "").strip()
    if sort == "oldest":
        journals = journals.order_by("date", "created_at")
    elif sort == "a_z":
        journals = journals.order_by("plant_name")
    elif sort == "z_a":
        journals = journals.order_by("-plant_name")
    else:
        journals = journals.order_by("-date", "-created_at")
    return journals


def _get_plant_books(request):
    """Mengelompokkan catatan per tanaman menjadi 'Buku Jurnal Tanaman'."""
    journals = _get_filtered_journals(request)

    # Ambil tanaman-tanaman unik
    plant_names = (
        journals.exclude(plant_name="")
        .values_list("plant_name", flat=True)
        .distinct()
        .order_by("plant_name")
    )

    books = []
    for p_name in plant_names:
        p_journals = journals.filter(plant_name=p_name).order_by("-date", "-created_at")
        latest = p_journals.first()
        if latest:
            cover_pattern = latest.cover_pattern or "flowers"
            _ds_badge_map = {
                "healthy": "healthy",
                "needs_attention": "attention",
                "wilting": "wilting",
                "flowering": "flowering",
                "fruiting": "planned",
                "ready_to_harvest": "healthy",
            }
            books.append({
                "plant_name": p_name,
                "count": p_journals.count(),
                "latest_date": latest.date,
                "latest_condition": latest.plant_condition,
                "condition_badge": latest.get_condition_display_badge,
                "condition_ds_badge": _ds_badge_map.get(latest.plant_condition, "attention"),
                "condition_display": latest.get_plant_condition_display(),
                "cover_pattern": cover_pattern,
                "cover_color": latest.cover_color or "",
                "ecopatch_name": latest.ecopatch_name,
                "latest_entry": latest,
            })

    # Sort books sesuai parameter sort
    sort = request.GET.get("sort", "").strip()
    if sort == "oldest":
        books.sort(key=lambda b: (b["latest_date"] or datetime.date.min, b["latest_entry"].created_at if b.get("latest_entry") else datetime.datetime.min))
    elif sort == "z_a":
        books.sort(key=lambda b: b["plant_name"].lower(), reverse=True)
    elif sort == "a_z":
        books.sort(key=lambda b: b["plant_name"].lower())
    else:
        # Default atau "newest": urutkan dari catatan terbaru
        books.sort(key=lambda b: (b["latest_date"] or datetime.date.min, b["latest_entry"].created_at if b.get("latest_entry") else datetime.datetime.min), reverse=True)

    return books


def _get_user_patch_plants(user):
    """Mengambil daftar nama tanaman milik user dari My EcoPatch.

    Opsi 2 (Fleksibel & Terintegrasi):
    Mengambil semua tanaman yang ada di My EcoPatch (Planned, Planted, Growing, Harvested)
    kecuali yang berstatus Removed. Pengguna dapat langsung menulis jurnal sejak tahap
    perencanaan bibit tanpa terblokir.
    """
    from my_ecopatch.models import PatchPlant
    patch_plants = (
        PatchPlant.objects.filter(patch__owner=user)
        .exclude(status=PatchPlant.Status.REMOVED)
        .select_related("plant", "patch")
        .order_by("patch__name", "plant__name", "plant_name")
    )
    seen = set()
    plants = []
    for pp in patch_plants:
        p_name = pp.plant.name if pp.plant_id else pp.plant_name
        if p_name and p_name not in seen:
            seen.add(p_name)
            plants.append(p_name)
    return plants


def _has_planned_plants(user):
    """Mengecek apakah user memiliki tanaman yang masih berstatus Planned."""
    from my_ecopatch.models import PatchPlant
    return PatchPlant.objects.filter(
        patch__owner=user, status=PatchPlant.Status.PLANNED
    ).exists()


@login_required
def journal_list(request):
    """Halaman utama Garden Journal dengan tampilan buku per tanaman."""
    from my_ecopatch.models import EcoPatch

    user_journals = GardenJournal.objects.filter(user=request.user)
    books = _get_plant_books(request)
    has_ecopatch = EcoPatch.objects.filter(owner=request.user).exists()
    user_plants = _get_user_patch_plants(request.user)
    has_planned_plants = _has_planned_plants(request.user)

    # Tampilkan filter foto hanya jika minimal 1 catatan sudah punya foto.
    # Ganti ini jadi True ketika fitur upload foto sudah aktif penuh.
    has_any_photo = user_journals.exclude(image="").exclude(image__isnull=True).exists()

    ecopatch_names = list(
        user_journals.exclude(ecopatch_name="")
        .values_list("ecopatch_name", flat=True)
        .distinct()
        .order_by("ecopatch_name")
    )
    active = {
        "ecopatch_name": request.GET.get("ecopatch_name", "").strip(),
        "plant_name": request.GET.get("plant_name", "").strip(),
        "condition": request.GET.get("condition", "").strip(),
        "has_photo": request.GET.get("has_photo", "").strip() if has_any_photo else "",
        "sort": request.GET.get("sort", "").strip(),
    }

    today = timezone.localdate()
    last_7_dates = [today - timedelta(days=i) for i in range(6, -1, -1)]
    journal_dates_set = set(
        user_journals.filter(date__in=last_7_dates).values_list("date", flat=True)
    )
    id_day_names = {0: "Sen", 1: "Sel", 2: "Rab", 3: "Kam", 4: "Jum", 5: "Sab", 6: "Min"}
    last_7_days = [
        {
            "date": d,
            "day_name": id_day_names.get(d.weekday(), d.strftime("%a")),
            "has_entry": d in journal_dates_set,
            "is_today": d == today,
        }
        for d in last_7_dates
    ]
    days_written_count = user_journals.values("date").distinct().count()

    context = {
        "books": books,
        "total_journals": user_journals.count(),
        "total_user_journals": user_journals.count(),
        "total_plants": len(books),
        "total_user_plants": len(user_plants),
        "days_written_count": days_written_count,
        "last_7_days": last_7_days,
        "ecopatch_names": ecopatch_names,
        "conditions": GardenJournal.CONDITION_CHOICES,
        "has_any_photo": has_any_photo,
        "filter_dropdowns": _journal_filter_dropdowns(
            active, ecopatch_names, GardenJournal.CONDITION_CHOICES,
            show_photo_filter=has_any_photo,
        ),
        "has_active_filters": bool(active["ecopatch_name"] or active["condition"] or active["has_photo"] or active["sort"]),
        "filters_reset_url": _journal_filter_url(
            active, ecopatch_name="", condition="", has_photo="", sort=""
        ),
        "search_clear_url": _journal_filter_url(active, plant_name=""),
        "selected_ecopatch_name": active["ecopatch_name"],
        "selected_plant_name": active["plant_name"],
        "selected_condition": active["condition"],
        "selected_has_photo": active["has_photo"],
        "selected_sort": active["sort"],
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
        "has_ecopatch": has_ecopatch,
        "has_user_plants": len(user_plants) > 0,
        "has_planned_plants": has_planned_plants,
        "user_plants": user_plants,
    }
    return render(request, "garden_journal/list.html", context)


@login_required
def journal_filter_ajax(request):
    """Endpoint untuk HTMX live search/filter tanpa reload halaman di rak buku."""
    user_journals = GardenJournal.objects.filter(user=request.user)
    books = _get_plant_books(request)
    user_plants = _get_user_patch_plants(request.user)
    return render(
        request,
        "garden_journal/partials/book_grid.html",
        {
            "books": books,
            "total_journals": user_journals.count(),
            "total_user_journals": user_journals.count(),
            "has_user_plants": len(user_plants) > 0,
            "user_plants": user_plants,
        },
    )


@login_required
def plant_journal_history(request, plant_name):
    """Membuka lembaran buku dua sisi (open book spread) untuk satu tanaman."""
    import json

    journals_query = GardenJournal.objects.filter(
        user=request.user, plant_name=plant_name
    ).order_by("-date", "-created_at")

    condition_filter = request.GET.get("condition", "").strip()
    if condition_filter:
        journals_query = journals_query.filter(plant_condition=condition_filter)

    parsed_date = _filter_date(request.GET.get("date", "").strip())
    date_filter = parsed_date.isoformat() if parsed_date else ""
    if parsed_date:
        journals_query = journals_query.filter(date=parsed_date)

    total_entries = journals_query.count()

    page_number = request.GET.get("page", 1)
    paginator = Paginator(journals_query, 1)
    page_obj = paginator.get_page(page_number)

    current_entry = page_obj.object_list[0] if page_obj.object_list else None

    # Serialise all entries for JS-driven page flip (client-side, no HTMX round trips)
    badge_map = {
        "healthy": "success",
        "needs_attention": "warning",
        "wilting": "danger",
        "flowering": "info",
        "fruiting": "primary",
        "ready_to_harvest": "secondary",
    }
    condition_label = {c[0]: c[1] for c in GardenJournal.CONDITION_CHOICES}

    # Plain Python data: the template embeds it with json_script, which escapes "</script>" and friends.
    all_entries = [
        {
            "id": j.pk,
            "pk": j.pk,
            "title": j.title,
            "notes": j.notes,
            "date": j.date.strftime("%d %b %Y"),
            "date_iso": j.date.isoformat(),
            "plant_height": j.plant_height,
            "ecopatch_name": j.ecopatch_name,
            "plant_condition": j.plant_condition,
            "condition_display": condition_label.get(j.plant_condition, j.plant_condition),
            "badge": badge_map.get(j.plant_condition, "secondary"),
            "edit_url": f"/journal/{j.pk}/edit/",
            "delete_url": f"/journal/{j.pk}/delete/",
            "upload_photo_url": f"/journal/{j.pk}/upload-photo/",
            "image_url": j.image.url if j.image else None,
            "created_at": j.created_at.strftime("%d %b %Y, %H:%M"),
        }
        for j in journals_query
    ]

    first_all = GardenJournal.objects.filter(user=request.user, plant_name=plant_name).order_by("-date").first()
    cover_pattern = first_all.cover_pattern if first_all else "flowers"
    cover_color = first_all.cover_color if first_all else ""

    # --- Stats for Riwayat dashboard ---
    all_unfiltered = GardenJournal.objects.filter(
        user=request.user, plant_name=plant_name
    ).order_by("date")

    # Latest and oldest height for growth calc
    entries_with_height = all_unfiltered.exclude(plant_height__isnull=True)
    latest_height = None
    growth = None
    if entries_with_height.exists():
        latest_h = entries_with_height.order_by("-date").first()
        oldest_h = entries_with_height.order_by("date").first()
        latest_height = latest_h.plant_height
        if latest_h != oldest_h:
            growth = round(latest_h.plant_height - oldest_h.plant_height, 1)

    # Chart data: height over time (ascending by date)
    chart_data = [
        {
            "date": j.date.strftime("%d %b %Y"),
            "date_iso": j.date.isoformat(),
            "height": j.plant_height,
        }
        for j in entries_with_height.order_by("date")
    ]

    context = {
        "plant_name": plant_name,
        "journals": journals_query,
        "total_entries": total_entries,
        "current_entry": current_entry,
        "page_obj": page_obj,
        "cover_pattern": cover_pattern,
        "cover_color": cover_color,
        "conditions": GardenJournal.CONDITION_CHOICES,
        "selected_condition": condition_filter,
        "selected_condition_label": dict(GardenJournal.CONDITION_CHOICES).get(condition_filter, ""),
        "selected_date": date_filter,
        "latest_condition": first_all.plant_condition if first_all else "healthy",
        "latest_badge": first_all.get_condition_display_badge if first_all else "success",
        "latest_ds_badge": first_all.get_condition_ds_class if first_all else "badge-ds-healthy",
        "latest_condition_display": first_all.get_plant_condition_display() if first_all else "Healthy",
        "all_entries": all_entries,
        "initial_page": 0,  # Selalu buka lembar catatan terkini (index 0)
        # stats
        "latest_height": latest_height,
        "growth": growth,
        "chart_data": chart_data,
    }

    # Jika request AJAX / HTMX untuk membalik lembar halaman buku
    if request.headers.get("HX-Request"):
        return render(request, "garden_journal/partials/book_spread_inner.html", context)

    return render(request, "garden_journal/plant_history.html", context)


@login_required
def journal_detail(request, pk):
    """Halaman detail catatan jurnal."""
    journal = get_object_or_404(GardenJournal, pk=pk, user=request.user)
    return render(request, "garden_journal/detail.html", {"journal": journal})


@login_required
def journal_create(request):
    """Menambah catatan jurnal baru dengan 2-step setup:
    Step 1: Setup EcoPatch, Tanaman, dan Sampul Buku
    Step 2: Catatan jurnal (kondisi, catatan, foto, tinggi, tanggal)
    """
    import json
    from datetime import date
    from my_ecopatch.models import EcoPatch

    user_patches = EcoPatch.objects.filter(owner=request.user).prefetch_related("plants__plant")
    has_ecopatch = user_patches.exists()

    initial_plant = request.GET.get("plant_name", "").strip() or request.POST.get("plant_name", "").strip()
    prev_journal = None
    is_adding_to_existing_book = False
    start_at_step_2 = False

    if initial_plant:
        prev_journal = GardenJournal.objects.filter(
            user=request.user, plant_name__iexact=initial_plant
        ).first()
        if prev_journal:
            is_adding_to_existing_book = True
            start_at_step_2 = True

    if request.method == "POST":
        form = GardenJournalForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            journal = form.save(commit=False)
            journal.user = request.user
            if not journal.ecopatch and journal.ecopatch_name:
                journal.ecopatch = user_patches.filter(name__iexact=journal.ecopatch_name.strip()).first()
            journal.save()
            messages.success(request, f"Catatan untuk '{journal.plant_name}' berhasil ditambahkan ke lembar buku!")
            return redirect("garden_journal:plant_history", plant_name=journal.plant_name)
        else:
            step1_fields = {"plant_name", "ecopatch_name", "cover_pattern"}
            has_step1_errors = any(f in form.errors for f in step1_fields)
            start_at_step_2 = not has_step1_errors or is_adding_to_existing_book
    else:
        initial_data = {"date": timezone.localdate()}
        if initial_plant:
            initial_data["plant_name"] = initial_plant
            if prev_journal:
                initial_data["plant_name"] = prev_journal.plant_name
                initial_data["cover_pattern"] = prev_journal.cover_pattern
                initial_data["cover_color"] = prev_journal.cover_color
                initial_data["ecopatch_name"] = prev_journal.ecopatch_name
        elif has_ecopatch:
            first_patch = user_patches.first()
            if first_patch:
                initial_data["ecopatch"] = first_patch.pk
                initial_data["ecopatch_name"] = first_patch.name
        form = GardenJournalForm(initial=initial_data, user=request.user)

    patch_plants_data = {}
    for patch in user_patches:
        plants = []
        for pp in patch.plants.all():
            p_name = pp.plant.name if pp.plant_id else pp.plant_name
            if p_name and p_name not in plants:
                plants.append(p_name)
        patch_plants_data[patch.name] = plants

    existing_books_data = {}
    for j in GardenJournal.objects.filter(user=request.user).order_by("created_at"):
        if j.plant_name:
            if j.plant_name not in existing_books_data:
                existing_books_data[j.plant_name] = {
                    "cover_pattern": j.cover_pattern or "soft",
                    "cover_color": j.cover_color or "",
                    "ecopatch_name": j.ecopatch_name or "",
                    "entry_count": 0,
                }
            existing_books_data[j.plant_name]["cover_pattern"] = j.cover_pattern or "soft"
            existing_books_data[j.plant_name]["cover_color"] = j.cover_color or ""
            existing_books_data[j.plant_name]["entry_count"] += 1

    return render(
        request,
        "garden_journal/form.html",
        {
            "form": form,
            "action": "Tambah",
            "journal": None,
            "has_ecopatch": has_ecopatch,
            "user_patches": user_patches,
            "patch_plants_json": json.dumps(patch_plants_data),
            "existing_books_json": json.dumps(existing_books_data),
            "start_at_step_2": start_at_step_2,
            "is_adding_to_existing_book": is_adding_to_existing_book,
            "initial_plant": initial_plant,
        },
    )


@login_required
def journal_edit(request, pk):
    """Mengedit catatan jurnal yang sudah ada. Langsung masuk ke Step 2 (Next)."""
    import json
    from my_ecopatch.models import EcoPatch

    journal = get_object_or_404(GardenJournal, pk=pk, user=request.user)
    user_patches = EcoPatch.objects.filter(owner=request.user).prefetch_related("plants__plant")

    if request.method == "POST":
        form = GardenJournalForm(request.POST, request.FILES, instance=journal, user=request.user)
        if form.is_valid():
            edited_journal = form.save(commit=False)
            if not edited_journal.ecopatch and edited_journal.ecopatch_name:
                edited_journal.ecopatch = user_patches.filter(name__iexact=edited_journal.ecopatch_name.strip()).first()
            edited_journal.save()
            messages.success(request, f"Catatan '{journal.title}' berhasil diperbarui.")
            return redirect("garden_journal:plant_history", plant_name=journal.plant_name)
    else:
        form = GardenJournalForm(instance=journal, user=request.user)

    patch_plants_data = {}
    for patch in user_patches:
        plants = []
        for pp in patch.plants.all():
            p_name = pp.plant.name if pp.plant_id else pp.plant_name
            if p_name and p_name not in plants:
                plants.append(p_name)
        patch_plants_data[patch.name] = plants

    return render(
        request,
        "garden_journal/form.html",
        {
            "form": form,
            "action": "Edit",
            "journal": journal,
            "has_ecopatch": True,
            "user_patches": user_patches,
            "patch_plants_json": json.dumps(patch_plants_data),
            "start_at_step_2": True,  # Edit selalu langsung buka step 2
            "initial_plant": journal.plant_name,
        },
    )


@login_required
@require_POST
def journal_delete(request, pk):
    """Menghapus catatan jurnal."""
    journal = get_object_or_404(GardenJournal, pk=pk, user=request.user)
    title = journal.title
    plant_name = journal.plant_name
    journal.delete()
    messages.success(request, f"Catatan '{title}' berhasil dihapus.")
    if GardenJournal.objects.filter(user=request.user, plant_name=plant_name).exists():
        return redirect("garden_journal:plant_history", plant_name=plant_name)
    return redirect("garden_journal:list")


@login_required
@require_POST
def journal_quick_upload_photo(request, pk):
    """Upload cepat foto tanaman langsung dari lembaran buku tanpa membuka form edit."""
    journal = get_object_or_404(GardenJournal, pk=pk, user=request.user)
    if "image" not in request.FILES:
        return JsonResponse({"success": False, "error": "Tidak ada file foto yang dipilih."}, status=400)

    image_file = request.FILES["image"]
    valid_content_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    if hasattr(image_file, "content_type") and image_file.content_type not in valid_content_types:
        return JsonResponse({"success": False, "error": "Format file harus JPG, PNG, atau WebP."}, status=400)

    try:
        image_file = GardenJournalForm.base_fields["image"].clean(image_file)
    except ValidationError as error:
        return JsonResponse({"success": False, "error": " ".join(error.messages)}, status=400)

    journal.image = image_file
    journal.save(update_fields=["image", "updated_at"])
    return JsonResponse({
        "success": True,
        "image_url": journal.image.url,
        "message": f"Foto untuk '{journal.title}' berhasil diunggah!",
    })
