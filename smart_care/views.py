from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CareTaskForm
from .models import CITY_CHOICES, DEFAULT_CITY, CareTask
from .services import CITY_COORDINATES, get_recommendation, get_weather


def _selected_city(request):
    """City from ?city=, else the city of the user's first task, else the default."""
    city = request.GET.get("city")
    if city in CITY_COORDINATES:
        return city
    first_task = CareTask.objects.filter(user=request.user).order_by("created_at").first()
    return first_task.city if first_task else DEFAULT_CITY


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _stats(user, city):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    tasks = CareTask.objects.filter(user=user, city=city)
    this_week = tasks.filter(due_date__range=(week_start, week_end))
    due_today = tasks.filter(due_date=today)

    today_total = due_today.count()
    today_completed = due_today.filter(is_completed=True).count()
    return {
        "today_total": today_total,
        "today_completed": today_completed,
        "today_percent": round(today_completed * 100 / today_total) if today_total else 0,
        "week_completed": this_week.filter(is_completed=True).count(),
        "week_pending": this_week.filter(is_completed=False, due_date__gte=today).count(),
        "overdue": tasks.filter(is_completed=False, due_date__lt=today).count(),
    }


def _list_url(city):
    return f"{reverse('smart_care:list')}?{urlencode({'city': city})}"


@login_required
def care_task_list(request):
    city = _selected_city(request)
    selected_date = _parse_date(request.GET.get("date"))

    tasks = CareTask.objects.filter(user=request.user, city=city)
    if selected_date:
        tasks = tasks.filter(due_date=selected_date)
    else:
        tasks = tasks.filter(due_date__gte=timezone.localdate())

    weather = get_weather(city)
    context = {
        "tasks": tasks.order_by("due_date", "is_completed", "created_at"),
        "city": city,
        "city_choices": CITY_CHOICES,
        "selected_date": selected_date,
        "weather": weather,
        "recommendation": get_recommendation(weather) if weather["available"] else None,
        "stats": _stats(request.user, city),
    }
    return render(request, "smart_care/list.html", context)


@login_required
def care_task_create(request):
    if request.method == "POST":
        form = CareTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, "Tugas perawatan ditambahkan.")
            return redirect(_list_url(task.city))
    else:
        initial = {"due_date": timezone.localdate(), "city": _selected_city(request)}
        form = CareTaskForm(initial=initial)
    return render(request, "smart_care/form.html", {"form": form, "is_edit": False})


@login_required
def care_task_update(request, pk):
    # Filtering by user makes other users' tasks a 404 rather than exposing that they exist
    task = get_object_or_404(CareTask, pk=pk, user=request.user)
    if request.method == "POST":
        form = CareTaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Tugas perawatan diperbarui.")
            return redirect(_list_url(task.city))
    else:
        form = CareTaskForm(instance=task)
    return render(request, "smart_care/form.html", {"form": form, "is_edit": True, "task": task})


@login_required
@require_POST
def care_task_delete(request, pk):
    task = get_object_or_404(CareTask, pk=pk, user=request.user)
    city = task.city
    task.delete()
    messages.success(request, "Tugas perawatan dihapus.")
    return redirect(_list_url(city))


@login_required
@require_POST
def care_task_complete(request, pk):
    task = get_object_or_404(CareTask, pk=pk, user=request.user)
    task.is_completed = not task.is_completed
    task.save(update_fields=["is_completed"])

    if not request.headers.get("HX-Request"):
        return redirect(_list_url(task.city))
    # The row replaces itself; the progress bar and weekly summary update out-of-band
    context = {"task": task, "stats": _stats(request.user, task.city), "oob": True}
    return render(request, "smart_care/_task_row.html", context)
