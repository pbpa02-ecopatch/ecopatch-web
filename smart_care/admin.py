from django.contrib import admin

from .models import CareTask


@admin.register(CareTask)
class CareTaskAdmin(admin.ModelAdmin):
    list_display = ("plant_name", "task_type", "user", "due_date", "status", "source")
    list_filter = ("task_type", "status", "source", "is_outdoor")
    search_fields = ("plant_name", "user__username", "notes")
    # raw_id_fields: patch_plant tampil sebagai kolom ID, bukan dropdown berisi semua tanaman semua user.
    raw_id_fields = ("patch_plant",)
    # Menambah navigasi tahun/bulan/hari di atas daftar, berdasarkan tanggal jatuh tempo.
    date_hierarchy = "due_date"
    # Diisi otomatis oleh sistem (set_status dan auto_now_add), jadi hanya boleh dibaca di admin.
    readonly_fields = ("completed_at", "created_at")
