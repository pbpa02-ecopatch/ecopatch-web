from django.contrib import admin

from .models import SeedExchange


@admin.register(SeedExchange)
class SeedExchangeAdmin(admin.ModelAdmin):
    list_display = ('title', 'item_type', 'transaction_type', 'status', 'city', 'user', 'reserved_by', 'contact', 'created_at')
    list_filter = ('item_type', 'transaction_type', 'status', 'city')
    search_fields = ('title', 'plant_name', 'description')
    readonly_fields = ('created_at', 'updated_at')
