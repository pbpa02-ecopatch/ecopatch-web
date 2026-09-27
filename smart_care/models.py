from django.conf import settings
from django.db import models

from .services import CITY_COORDINATES

CITY_CHOICES = [(city, city) for city in CITY_COORDINATES]
DEFAULT_CITY = "Depok"


class CareTask(models.Model):
    TASK_CHOICES = [
        ("watering", "Watering"),
        ("fertilizing", "Fertilizing"),
        ("pruning", "Pruning"),
        ("repotting", "Repotting"),
        ("harvesting", "Harvesting"),
        ("inspection", "Inspection"),
    ]

    # TODO(smart_care): my_ecopatch belum punya model EcoPatch/PatchPlant. Begitu modul
    # itu selesai, ganti `user` + `city` dengan ForeignKey ke my_ecopatch.PatchPlant;
    # kepemilikan lalu dicek lewat patch_plant.ecopatch.user dan kota lewat
    # patch_plant.ecopatch.city.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="care_tasks",
    )
    city = models.CharField(max_length=50, choices=CITY_CHOICES, default=DEFAULT_CITY)
    task_type = models.CharField(max_length=20, choices=TASK_CHOICES)
    due_date = models.DateField()
    is_completed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "is_completed", "created_at"]

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.due_date}"
