from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CareTaskForm
from .models import CareTask
from .services import CITY_COORDINATES, DEFAULT_CITY, get_care_recommendation, get_weather_data


@login_required
def care_task_list(request):
    tasks = CareTask.objects.filter(user=request.user)

    due_date = request.GET.get("due_date")
    if due_date:
        tasks = tasks.filter(due_date=due_date)

    city = request.GET.get("city") or DEFAULT_CITY
    if city not in CITY_COORDINATES:
        city = DEFAULT_CITY

    weather = get_weather_data(city)
    recommendations = get_care_recommendation(weather)

    context = {
        "tasks": tasks,
        "cities": sorted(CITY_COORDINATES.keys()),
        "selected_city": city,
        "weather": weather,
        "recommendations": recommendations,
        "selected_date": due_date or "",
    }
    return render(request, "smart_care/list.html", context)


@login_required
def care_task_detail(request, pk):
    task = get_object_or_404(CareTask, pk=pk, user=request.user)
    return render(request, "smart_care/detail.html", {"task": task})


@login_required
def care_task_create(request):
    if request.method == "POST":
        form = CareTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            return redirect("smart_care:list")
    else:
        form = CareTaskForm()
    return render(request, "smart_care/form.html", {"form": form, "is_edit": False})


@login_required
def care_task_update(request, pk):
    task = get_object_or_404(CareTask, pk=pk, user=request.user)
    if request.method == "POST":
        form = CareTaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            return redirect("smart_care:detail", pk=task.pk)
    else:
        form = CareTaskForm(instance=task)
    return render(request, "smart_care/form.html", {"form": form, "is_edit": True, "task": task})


@login_required
def care_task_delete(request, pk):
    task = get_object_or_404(CareTask, pk=pk, user=request.user)
    if request.method == "POST":
        task.delete()
        return redirect("smart_care:list")
    return render(request, "smart_care/confirm_delete.html", {"task": task})


@login_required
@require_POST
def care_task_complete(request, pk):
    task = get_object_or_404(CareTask, pk=pk, user=request.user)
    task.is_completed = True
    task.save()
    return render(request, "smart_care/partials/task_row.html", {"task": task})
