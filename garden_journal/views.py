from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import GardenJournalForm
from .models import GardenJournal


def _get_filtered_journals(request):
    """Helper query filter untuk list dan AJAX live filter."""
    journals = GardenJournal.objects.filter(user=request.user)

    ecopatch_name = request.GET.get("ecopatch_name", "").strip()
    plant_name = request.GET.get("plant_name", "").strip()
    condition = request.GET.get("condition", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if ecopatch_name:
        journals = journals.filter(ecopatch_name__icontains=ecopatch_name)
    if plant_name:
        journals = journals.filter(plant_name__icontains=plant_name)
    if condition:
        journals = journals.filter(plant_condition=condition)
    if date_from:
        journals = journals.filter(date__gte=date_from)
    if date_to:
        journals = journals.filter(date__lte=date_to)

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
            books.append({
                "plant_name": p_name,
                "count": p_journals.count(),
                "latest_date": latest.date,
                "latest_condition": latest.plant_condition,
                "condition_badge": latest.get_condition_display_badge,
                "condition_display": latest.get_plant_condition_display(),
                "cover_pattern": cover_pattern,
                "ecopatch_name": latest.ecopatch_name,
                "latest_entry": latest,
            })
    return books


@login_required
def journal_list(request):
    """Halaman utama Garden Journal dengan tampilan buku per tanaman."""
    user_journals = GardenJournal.objects.filter(user=request.user)
    books = _get_plant_books(request)

    ecopatch_names = (
        user_journals.exclude(ecopatch_name="")
        .values_list("ecopatch_name", flat=True)
        .distinct()
    )

    context = {
        "books": books,
        "total_journals": user_journals.count(),
        "total_plants": len(books),
        "ecopatch_names": ecopatch_names,
        "conditions": GardenJournal.CONDITION_CHOICES,
        "selected_ecopatch_name": request.GET.get("ecopatch_name", ""),
        "selected_plant_name": request.GET.get("plant_name", ""),
        "selected_condition": request.GET.get("condition", ""),
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
    }
    return render(request, "garden_journal/list.html", context)


@login_required
def journal_filter_ajax(request):
    """Endpoint untuk HTMX live search/filter tanpa reload halaman di rak buku."""
    books = _get_plant_books(request)
    return render(request, "garden_journal/partials/book_grid.html", {"books": books})


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

    date_filter = request.GET.get("date", "").strip()
    if date_filter:
        journals_query = journals_query.filter(date=date_filter)

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

    all_entries_json = json.dumps([
        {
            "pk": j.pk,
            "title": j.title,
            "notes": j.notes,
            "date": j.date.strftime("%d %b %Y"),
            "plant_height": j.plant_height,
            "ecopatch_name": j.ecopatch_name,
            "plant_condition": j.plant_condition,
            "condition_display": condition_label.get(j.plant_condition, j.plant_condition),
            "badge": badge_map.get(j.plant_condition, "secondary"),
            "edit_url": f"/journal/{j.pk}/edit/",
            "delete_url": f"/journal/{j.pk}/delete/",
        }
        for j in journals_query
    ])

    first_all = GardenJournal.objects.filter(user=request.user, plant_name=plant_name).order_by("-date").first()
    cover_pattern = first_all.cover_pattern if first_all else "flowers"

    context = {
        "plant_name": plant_name,
        "journals": journals_query,
        "total_entries": total_entries,
        "current_entry": current_entry,
        "page_obj": page_obj,
        "cover_pattern": cover_pattern,
        "conditions": GardenJournal.CONDITION_CHOICES,
        "selected_condition": condition_filter,
        "selected_date": date_filter,
        "latest_condition": first_all.plant_condition if first_all else "healthy",
        "latest_badge": first_all.get_condition_display_badge if first_all else "success",
        "latest_condition_display": first_all.get_plant_condition_display() if first_all else "Healthy",
        "all_entries_json": all_entries_json,
        "initial_page": int(page_obj.number) - 1,  # 0-indexed for JS
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
    """Menambah catatan jurnal baru."""
    initial_plant = request.GET.get("plant_name", "")
    if request.method == "POST":
        form = GardenJournalForm(request.POST)
        if form.is_valid():
            journal = form.save(commit=False)
            journal.user = request.user
            journal.save()
            messages.success(request, f"Catatan untuk '{journal.plant_name}' berhasil ditambahkan ke lembar buku! 🌿")
            return redirect("garden_journal:plant_history", plant_name=journal.plant_name)
    else:
        initial_data = {}
        if initial_plant:
            initial_data["plant_name"] = initial_plant
            prev = GardenJournal.objects.filter(user=request.user, plant_name=initial_plant).first()
            if prev:
                initial_data["cover_pattern"] = prev.cover_pattern
                initial_data["ecopatch_name"] = prev.ecopatch_name
        form = GardenJournalForm(initial=initial_data)

    return render(
        request,
        "garden_journal/form.html",
        {
            "form": form,
            "action": "Tambah",
            "journal": None,
        },
    )


@login_required
def journal_edit(request, pk):
    """Mengedit catatan jurnal yang sudah ada."""
    journal = get_object_or_404(GardenJournal, pk=pk, user=request.user)

    if request.method == "POST":
        form = GardenJournalForm(request.POST, instance=journal)
        if form.is_valid():
            form.save()
            messages.success(request, f"Catatan '{journal.title}' berhasil diperbarui.")
            return redirect("garden_journal:plant_history", plant_name=journal.plant_name)
    else:
        form = GardenJournalForm(instance=journal)

    return render(
        request,
        "garden_journal/form.html",
        {
            "form": form,
            "action": "Edit",
            "journal": journal,
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
