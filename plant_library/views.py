from django.shortcuts import get_object_or_404, render
from .models import Plant


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
