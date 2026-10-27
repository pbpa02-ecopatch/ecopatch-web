from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import CareTaskForm
from .models import CareTask
from .plant_source import (
    find_patch_plant,
    get_user_city,
    get_user_plants,
    get_user_watering_days,
    is_outdoor,
    patch_plant_name,
)
from .suggestions import INTERVALS, HistoryEntry, build_suggestions, normalize, plant_status
from .weather import CITIES, DEFAULT_CITY, FORECAST_DAYS, WeatherUnavailable, weather_payload

STRIP_DOTS = 3  # a day of the week strip shows up to this many dots, then "+N"
Status = CareTask.Status

# One tip under the page, picked by the day of the month of the selected date
TIPS = (
    "Siram di pagi hari, bukan siang bolong. Air lebih sempat diserap sebelum panas.",
    "Cek tanah dengan jari: kalau 2 cm teratas masih lembap, tunda menyiram.",
    "Pupuk cair paling baik diberikan saat tanah sudah sedikit lembap, bukan kering kerontang.",
    "Putar pot indoor seperempat putaran tiap minggu supaya daunnya tumbuh seimbang.",
    "Daun menguning bisa tanda kelebihan air. Cek lubang drainase potmu.",
    "Pangkas ujung tunas basil supaya ia tumbuh bercabang dan makin rimbun.",
    "Hujan deras bisa mencuci pupuk dari tanah. Tunda pemupukan outdoor setelah hujan.",
)

# Before there is any plant the tip stays general: nothing that talks about a particular plant or pot
GENERAL_TIPS = TIPS[:3]


def _profile_city(user):
    """City saved on the user's profile, if the profile feature exists and has one."""
    try:
        return user.profile.city
    except (AttributeError, ObjectDoesNotExist):
        return ""


def _current_city(user):
    """The profile city, else the city an older EcoPatch still carries, else Depok. The user does not pick it here."""
    for city in (_profile_city(user), get_user_city(user)):
        if city in CITIES:
            return city
    return DEFAULT_CITY


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _list_url(day=None):
    url = reverse("smart_care:list")
    return f"{url}?{urlencode({'date': day.isoformat()})}" if day else url


# ---------------------------------------------------------------- suggestions + progress
def _history(user, today):
    """Completed tasks (for the interval rule) plus everything dated today (so nothing is suggested twice)."""
    rows = CareTask.objects.filter(user=user).filter(Q(status=Status.COMPLETED) | Q(due_date=today))
    entries = []
    for task in rows:
        completed_on = None
        if task.status == Status.COMPLETED:
            completed_on = timezone.localtime(task.completed_at).date() if task.completed_at else task.due_date
        entries.append(HistoryEntry(task.plant_name, task.task_type, task.status, task.due_date, completed_on))
    return entries


def _suggestions_for_today(user, today, plants=None, watering_days=None):
    plants = get_user_plants(user) if plants is None else plants
    watering_days = get_user_watering_days(user) if watering_days is None else watering_days
    return build_suggestions(plants, _history(user, today), today, watering_days=watering_days)


def _pots(plants, history, today, watering_days=None):
    return [plant_status(plant, history, today, watering_days=watering_days) for plant in plants]


def _day_state(user, day, today, plants=None, watering_days=None):
    """The visible tasks of one day (skipped ones hidden) and, for today only, the open suggestions."""
    tasks = [t for t in CareTask.objects.filter(user=user, due_date=day).order_by("created_at") if t.status != Status.SKIPPED]
    suggestions = _suggestions_for_today(user, today, plants, watering_days) if day == today else []
    return tasks, suggestions


def _progress(tasks, suggestions):
    """Completed items over all items of the day (tasks + open suggestions, skipped excluded),
    plus the growth stage of the daily plant: 0 seed, 1 sprout, 2 leaves, 3 flower."""
    total = len(tasks) + len(suggestions)
    done = sum(1 for task in tasks if task.status == Status.COMPLETED)
    percent = round(done * 100 / total) if total else 0
    if total and percent == 100:
        stage = 3
    elif percent >= 50:
        stage = 2
    elif percent > 0:
        stage = 1
    else:
        stage = 0
    return {"total": total, "done": done, "pending": total - done, "percent": percent, "stage": stage}


def _week_strip(user, selected, today, open_suggestions):
    """The Monday to Sunday week of the selected day. Each day has dots for its tasks: done, still to do, or late."""
    first = selected - timedelta(days=selected.weekday())
    rows = (
        CareTask.objects.filter(user=user, due_date__range=(first, first + timedelta(days=6)))
        .exclude(status=Status.SKIPPED)
        .order_by("created_at", "pk")
        .values_list("due_date", "status")
    )
    by_day = {}
    for day, status in rows:
        by_day.setdefault(day, []).append("done" if status == Status.COMPLETED else "late" if day < today else "pending")

    strip = []
    for offset in range(7):
        day = first + timedelta(days=offset)
        dots = list(by_day.get(day, []))
        if day == today:
            # open suggestions only exist for today, so they only add to today's dots
            dots += ["pending"] * open_suggestions
        strip.append({
            "date": day,
            "pending": sum(1 for dot in dots if dot != "done"),
            "dots": dots[:STRIP_DOTS],
            "more": max(0, len(dots) - STRIP_DOTS),
            "is_selected": day == selected,
            "is_today": day == today,
            "url": _list_url(day),
        })
    return strip


def _overdue(user, today):
    """Pending tasks from before today, oldest first, each knowing how many days late it is."""
    tasks = list(CareTask.objects.filter(user=user, status=Status.PENDING, due_date__lt=today).order_by("due_date"))
    for task in tasks:
        task.days_late = (today - task.due_date).days
    return tasks


def _skipped_suggestions(user, today):
    return CareTask.objects.filter(user=user, due_date=today, status=Status.SKIPPED, source=CareTask.Source.SUGGESTED)


# ---------------------------------------------------------------- pages
@login_required
def care_task_list(request):
    today = timezone.localdate()
    selected = _parse_date(request.GET.get("date")) or today
    plants = get_user_plants(request.user)
    watering_days = get_user_watering_days(request.user)
    tips = TIPS if plants else GENERAL_TIPS
    tasks, suggestions = _day_state(request.user, selected, today, plants, watering_days)
    for suggestion in suggestions:
        suggestion["label"] = CareTask.TaskType(suggestion["task_type"]).label
    is_today = selected == today

    context = {
        "selected_date": selected,
        "today": today,
        "is_today": is_today,
        # the forecast reaches from today to six days ahead; any other day has none
        "in_forecast": 0 < (selected - today).days < FORECAST_DAYS,
        "pending_tasks": [t for t in tasks if t.status == Status.PENDING],
        "done_tasks": [t for t in tasks if t.status == Status.COMPLETED],
        "suggestions": suggestions,
        "skipped_suggestions": list(_skipped_suggestions(request.user, today)) if is_today else [],
        "has_plants": bool(plants),
        "pots": _pots(plants, _history(request.user, today), today, watering_days),
        # Overdue tasks only show up when looking at today
        "overdue_tasks": _overdue(request.user, today) if is_today else [],
        "progress": _progress(tasks, suggestions),
        "strip": _week_strip(request.user, selected, today, len(suggestions)),
        "prev_week_url": _list_url(selected - timedelta(days=7)),
        "next_week_url": _list_url(selected + timedelta(days=7)),
        "today_url": _list_url(),
        "tip": tips[selected.day % len(tips)],
        "city": _current_city(request.user),
    }
    return render(request, "smart_care/list.html", context)


@login_required
@require_GET
def weather(request):
    """Weather + advice as JSON for the user's own city; the city cannot be chosen through the URL."""
    city = _current_city(request.user)
    try:
        return JsonResponse(weather_payload(city))
    except WeatherUnavailable:
        return JsonResponse(
            {"available": False, "city": city, "message": "Cuaca belum bisa dimuat."},
            status=503,
        )


def _form_response(request, form, **extra):
    """Popup (HTMX) gets only the modal content; a normal request gets the full page."""
    template = "smart_care/_task_form.html" if request.headers.get("HX-Request") else "smart_care/form.html"
    return render(request, template, {"form": form, **extra})


def _saved_response(request, day):
    """After a save: HTMX reloads the list (messages show up there), others redirect."""
    if request.headers.get("HX-Request"):
        return HttpResponse(status=204, headers={"HX-Redirect": _list_url(day)})
    return redirect(_list_url(day))


@login_required
def care_task_create(request):
    if request.method == "POST":
        form = CareTaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, "Tugas perawatan ditambahkan.")
            return _saved_response(request, task.due_date)
    else:
        form = CareTaskForm(initial={"due_date": _parse_date(request.GET.get("date")) or timezone.localdate()}, user=request.user)
    return _form_response(request, form, is_edit=False)


@login_required
def care_task_update(request, pk):
    # Filtering by user makes other users' tasks a 404 rather than exposing that they exist
    task = get_object_or_404(CareTask, pk=pk, user=request.user)
    if request.method == "POST":
        form = CareTaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Tugas perawatan diperbarui.")
            return _saved_response(request, task.due_date)
    else:
        form = CareTaskForm(instance=task, user=request.user)
    return _form_response(request, form, is_edit=True, task=task)


@login_required
@require_POST
def care_task_delete(request, pk):
    task = get_object_or_404(CareTask, pk=pk, user=request.user)
    day = task.due_date
    task.delete()
    messages.success(request, "Tugas perawatan dihapus.")
    return redirect(_list_url(day))


# ---------------------------------------------------------------- AJAX endpoints (JSON)
def _state_payload(user, task):
    """Shared by toggle, accept and skip, so the JS can reuse one handler for all three."""
    today = timezone.localdate()
    watering_days = get_user_watering_days(user)
    tasks, suggestions = _day_state(user, task.due_date, today, watering_days=watering_days)
    # the plant's pot changes when its watering / fertilizing / inspection is ticked
    wanted = normalize(task.plant_name)
    plants = [plant for plant in get_user_plants(user) if normalize(plant[0]) == wanted]
    return {
        "pot": _pots(plants, _history(user, today), today, watering_days)[0] if plants else None,
        "id": task.pk,
        "status": task.status,
        "is_completed": task.is_completed,
        "due_date": task.due_date.isoformat(),
        "progress": _progress(tasks, suggestions),
    }


@login_required
@require_POST
def care_task_complete(request, pk):
    """Flip a task between pending and completed. Skipped tasks cannot be toggled."""
    task = get_object_or_404(CareTask, pk=pk, user=request.user)
    if task.status == Status.SKIPPED:
        return JsonResponse({"error": "Tugas ini sudah dilewati."}, status=409)
    task.toggle()
    return JsonResponse(_state_payload(request.user, task))


def _valid_suggestion(request):
    """(patch_plant, task_type) when the posted pair belongs to this user and can be suggested."""
    task_type = request.POST.get("task_type", "")
    if task_type not in INTERVALS:
        return None
    patch_plant = find_patch_plant(request.user, request.POST.get("plant_name", ""))
    return (patch_plant, task_type) if patch_plant else None


def _suggestion_task(request, status):
    """Create today's task for an accepted / skipped suggestion. Repeating the call never makes a second one:
    an existing task for the same plant and type today (any status) is returned untouched."""
    found = _valid_suggestion(request)
    if found is None:
        return None, False
    patch_plant, task_type = found
    plant_name = patch_plant_name(patch_plant)
    today = timezone.localdate()
    for existing in CareTask.objects.filter(user=request.user, due_date=today, task_type=task_type):
        if normalize(existing.plant_name) == normalize(plant_name):
            return existing, False
    # get_or_create + the partial unique constraint cover a double click racing past the check above
    task, created = CareTask.objects.get_or_create(
        user=request.user,
        plant_name=plant_name,
        task_type=task_type,
        due_date=today,
        source=CareTask.Source.SUGGESTED,
        defaults={
            "patch_plant": patch_plant,
            "is_outdoor": is_outdoor(patch_plant),
            "status": status,
            "completed_at": timezone.now() if status == Status.COMPLETED else None,
        },
    )
    return task, created


@login_required
@require_POST
def suggestion_accept(request):
    task, created = _suggestion_task(request, Status.COMPLETED)
    if task is None:
        return JsonResponse({"error": "Saran tidak dikenali."}, status=400)
    payload = _state_payload(request.user, task)
    # The row is replaced by a real task row (with edit / delete) rendered by the same template
    payload.update(created=created, html=render_to_string("smart_care/_task_item.html", {"task": task}, request))
    return JsonResponse(payload)


@login_required
@require_POST
def suggestion_skip(request):
    task, created = _suggestion_task(request, Status.SKIPPED)
    if task is None:
        return JsonResponse({"error": "Saran tidak dikenali."}, status=400)
    payload = _state_payload(request.user, task)
    payload.update(
        created=created,
        skipped={
            "plant_name": task.plant_name,
            "task_type": task.task_type,
            "label": task.get_task_type_display(),
            "restore_url": reverse("smart_care:suggestion_restore"),
        },
    )
    return JsonResponse(payload)


@login_required
@require_POST
def suggestion_restore(request):
    """Undo a skip: the skipped record is removed, so the suggestion comes back on the next load."""
    found = _valid_suggestion(request)
    if found is None:
        return JsonResponse({"error": "Saran tidak dikenali."}, status=400)
    patch_plant, task_type = found
    plant_name = patch_plant_name(patch_plant)
    skipped = [
        task for task in _skipped_suggestions(request.user, timezone.localdate()).filter(task_type=task_type)
        if normalize(task.plant_name) == normalize(plant_name)
    ]
    for task in skipped:
        task.delete()
    return JsonResponse({"restored": bool(skipped)})
