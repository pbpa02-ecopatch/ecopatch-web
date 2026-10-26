from django.contrib import admin

from .models import CareTask


@admin.register(CareTask)
class CareTaskAdmin(admin.ModelAdmin):
    list_display = ("plant_name", "task_type", "user", "due_date", "status", "source")
    list_filter = ("task_type", "status", "source", "is_outdoor")
    search_fields = ("plant_name", "user__username", "notes")
    raw_id_fields = ("patch_plant",)
    date_hierarchy = "due_date"
    readonly_fields = ("completed_at", "created_at")
