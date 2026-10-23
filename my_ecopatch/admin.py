from django.contrib import admin

from .models import EcoPatch, PatchPlant


class PatchPlantInline(admin.TabularInline):
    model = PatchPlant
    extra = 0


@admin.register(EcoPatch)
class EcoPatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'space_type', 'city', 'created_at')
    list_filter = ('space_type',)
    inlines = [PatchPlantInline]
