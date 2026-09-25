from django.contrib import admin

from .models import CareTask


@admin.register(CareTask)
class CareTaskAdmin(admin.ModelAdmin):
    list_display = ("task_type", "due_date", "is_completed", "user")
    list_filter = ("task_type", "is_completed", "due_date")
    search_fields = ("notes",)
