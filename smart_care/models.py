from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


# CareTask: satu tugas perawatan milik satu user, untuk satu tanaman, pada satu tanggal
# (contoh: "Cabai - Penyiraman - 28 Okt"). Tugas berasal dari dua jalur:
#   manual    -> dibuat user lewat form popup (CareTaskForm)
#   suggested -> dibuat saat user menerima atau melewati saran harian (suggestions.py + views.suggestion_*)
# Model ini tidak menyimpan data tanaman maupun kota. Tanaman dibaca dari My EcoPatch (plant_source.py),
# kota dari Profile (views._current_city). Smart Care hanya mencatat apa yang sudah dijadwalkan dan dikerjakan.
class CareTask(models.Model):
    # Nilai kiri disimpan di database, nilai kanan ditampilkan ke user (get_task_type_display()).
    class TaskType(models.TextChoices):
        WATERING = "watering", "Penyiraman"
        FERTILIZING = "fertilizing", "Pemupukan"
        PRUNING = "pruning", "Pemangkasan"
        REPOTTING = "repotting", "Ganti pot"
        HARVESTING = "harvesting", "Panen"
        INSPECTION = "inspection", "Pemeriksaan"

    # Status menentukan tempat tampil tugas: pending -> daftar hari itu (atau "Terlewat" bila tanggalnya sudah lewat),
    # completed -> grup "Selesai", skipped -> hanya dipakai saran yang dilewati; tidak ditampilkan dan tidak dihitung progress.
    class Status(models.TextChoices):
        PENDING = "pending", "Belum selesai"
        COMPLETED = "completed", "Selesai"
        SKIPPED = "skipped", "Dilewati"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        SUGGESTED = "suggested", "Saran"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="care_tasks",
    )
    # Tanaman di My EcoPatch yang menjadi sasaran tugas ini. CASCADE: bila tanaman (atau EcoPatch yang memuatnya)
    # dihapus dari My EcoPatch, tugas perawatannya ikut terhapus. Tugas untuk tanaman yang sudah tidak ada tidak
    # berguna lagi, dan yang masih pending akan menumpuk di daftar "Terlewat". Mengubah status tanaman menjadi
    # "removed" bukan penghapusan (barisnya masih ada), jadi tugasnya tetap tersimpan.
    # null=True tetap diperlukan: tugas lama yang dibuat sebelum Smart Care membaca My EcoPatch, dan tidak bisa
    # dicocokkan ke tanaman (migrasi 0004), tidak punya tautan. Tugas seperti itu tidak ikut terhapus.
    # plant_name dan is_outdoor tetap disalin saat tautan dibuat (plant_source.link_task), supaya nama di riwayat
    # tidak berubah ketika nama tanaman di Plant Library diganti.
    patch_plant = models.ForeignKey(
        "my_ecopatch.PatchPlant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="care_tasks",
    )
    plant_name = models.CharField(max_length=80)
    task_type = models.CharField(max_length=20, choices=TaskType.choices)
    # default dipasang tanpa tanda kurung: fungsi dipanggil tiap objek baru dibuat (hari ini menurut zona waktu proyek),
    # bukan sekali saat server start.
    due_date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)
    # Indoor plants never get rain advice
    is_outdoor = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Suggested tasks are created when the user accepts or skips a suggestion
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Urutan bawaan setiap query CareTask: tanggal terdekat dulu, lalu yang dibuat lebih awal.
        ordering = ["due_date", "created_at"]
        constraints = [
            # A double click or a retry can never create the same suggestion twice on one day.
            # Kuncinya baris tanaman (patch_plant), bukan nama: Basil di kamar dan Basil di balkon adalah dua tanaman
            # yang masing-masing boleh punya satu saran per jenis per hari. Tugas lama tanpa tautan (patch_plant NULL)
            # tidak terkena, karena nilai NULL tidak dianggap sama oleh constraint unik.
            models.UniqueConstraint(
                fields=["user", "patch_plant", "task_type", "due_date"],
                condition=Q(source="suggested"),
                name="smart_care_one_suggestion_per_day",
            ),
        ]

    def __str__(self):
        return f"{self.plant_name}: {self.get_task_type_display()} ({self.due_date})"

    @property
    def is_completed(self):
        return self.status == self.Status.COMPLETED

    def set_status(self, status):
        # completed_at hanya terisi selama statusnya completed. Dikembalikan ke pending, nilainya dikosongkan lagi.
        # update_fields membatasi UPDATE ke dua kolom ini, jadi field lain tidak ikut tertimpa.
        self.status = status
        self.completed_at = timezone.now() if status == self.Status.COMPLETED else None
        self.save(update_fields=["status", "completed_at"])

    def toggle(self):
        """Flip pending and completed. Skipped tasks are left alone."""
        # View sudah menolak task skipped dengan 409 sebelum sampai sini. Pengecekan ini menjaga model tetap
        # benar bila toggle() dipanggil dari tempat lain (shell, tes, kode baru).
        if self.status == self.Status.SKIPPED:
            raise ValueError("Skipped tasks cannot be toggled")
        self.set_status(self.Status.PENDING if self.is_completed else self.Status.COMPLETED)
