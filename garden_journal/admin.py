from django.contrib import admin

from .models import GardenJournal


@admin.register(GardenJournal)
class GardenJournalAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "date", "plant_condition", "plant_name", "ecopatch_name")
    list_filter = ("plant_condition", "date")
    search_fields = ("title", "notes", "plant_name", "ecopatch_name", "user__username")
