from django.contrib import admin

from .models import CareTask


@admin.register(CareTask)
class CareTaskAdmin(admin.ModelAdmin):
    list_display = ("task_type", "user", "city", "due_date", "is_completed")
    list_filter = ("task_type", "is_completed", "city")
    search_fields = ("user__username", "notes")
    date_hierarchy = "due_date"
