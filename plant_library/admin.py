from django.contrib import admin
from .models import Plant


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'scientific_name',
        'category',
        'sunlight',
        'watering',
        'difficulty',
        'indoor_outdoor',
        'space_requirement',
    )
    list_filter = (
        'category',
        'sunlight',
        'watering',
        'difficulty',
        'indoor_outdoor',
        'space_requirement',
    )
    search_fields = ('name', 'scientific_name', 'description')

