from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CareTask(models.Model):
    class TaskType(models.TextChoices):
        WATERING = "watering", "Watering"
        FERTILIZING = "fertilizing", "Fertilizing"
        PRUNING = "pruning", "Pruning"
        REPOTTING = "repotting", "Repotting"
        HARVESTING = "harvesting", "Harvesting"
        INSPECTION = "inspection", "Inspection"

    class Status(models.TextChoices):
        PENDING = "pending", "Belum selesai"
        COMPLETED = "completed", "Selesai"
        SKIPPED = "skipped", "Dilewati"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        SUGGESTED = "suggested", "Saran"

    # TODO(smart_care): my_ecopatch belum punya model PatchPlant. Begitu modul itu selesai,
    # ganti `plant_name` dengan ForeignKey ke my_ecopatch.PatchPlant; kepemilikan lalu dicek
    # lewat patch_plant.ecopatch.user dan `is_outdoor` bisa diambil dari ecopatch.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="care_tasks",
    )
    plant_name = models.CharField(max_length=80)
    task_type = models.CharField(max_length=20, choices=TaskType.choices)
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
        ordering = ["due_date", "created_at"]
        constraints = [
            # A double click or a retry can never create the same suggestion twice on one day
            models.UniqueConstraint(
                fields=["user", "plant_name", "task_type", "due_date"],
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
        self.status = status
        self.completed_at = timezone.now() if status == self.Status.COMPLETED else None
        self.save(update_fields=["status", "completed_at"])

    def toggle(self):
        """Flip pending and completed. Skipped tasks are left alone."""
        if self.status == self.Status.SKIPPED:
            raise ValueError("Skipped tasks cannot be toggled")
        self.set_status(self.Status.PENDING if self.is_completed else self.Status.COMPLETED)
