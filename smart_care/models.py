from django.conf import settings
from django.db import models


class CareTask(models.Model):
    TASK_CHOICES = [
        ("watering", "Watering"),
        ("fertilizing", "Fertilizing"),
        ("pruning", "Pruning"),
        ("repotting", "Repotting"),
        ("harvesting", "Harvesting"),
        ("inspection", "Inspection"),
    ]

    # TODO: sambungkan ke my_ecopatch.PatchPlant begitu modul itu siap,
    # lalu filter user lewat patch_plant__ecopatch__user. Untuk sekarang
    # CareTask dikaitkan langsung ke User supaya modul ini tidak
    # menyentuh model my_ecopatch milik PIC lain.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="care_tasks")
    task_type = models.CharField(max_length=20, choices=TASK_CHOICES)
    due_date = models.DateField()
    is_completed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["due_date", "id"]

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.due_date}"
