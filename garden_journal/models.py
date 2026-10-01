from django.contrib.auth.models import User
from django.db import models


class GardenJournal(models.Model):
    CONDITION_CHOICES = [
        ("healthy", "Healthy"),
        ("needs_attention", "Needs Attention"),
        ("wilting", "Wilting"),
        ("flowering", "Flowering"),
        ("fruiting", "Fruiting"),
        ("ready_to_harvest", "Ready to Harvest"),
    ]

    COVER_CHOICES = [
        ("brushes", "Brushes"),
        ("dots", "Dots"),
        ("flowers", "Flowers"),
        ("seeds", "Seeds"),
        ("soft", "Soft"),
        ("leaves", "Leaves"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="garden_journals")
    ecopatch_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Nama EcoPatch (sementara, akan diganti FK ke EcoPatch)",
    )
    plant_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Nama tanaman (sementara, akan diganti FK ke Plant)",
    )
    date = models.DateField()
    title = models.CharField(max_length=200)
    notes = models.TextField()
    plant_condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default="healthy",
    )
    plant_height = models.FloatField(
        blank=True,
        null=True,
        help_text="Tinggi tanaman (cm), opsional",
    )
    cover_pattern = models.CharField(
        max_length=20,
        choices=COVER_CHOICES,
        default="flowers",
        help_text="Sampul buku jurnal",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.title} ({self.date})"

    @property
    def get_condition_display_badge(self):
        """Mapping status condition ke warna Bootstrap badge."""
        badge_map = {
            "healthy": "success",
            "needs_attention": "warning",
            "wilting": "danger",
            "flowering": "info",
            "fruiting": "primary",
            "ready_to_harvest": "secondary",
        }
        return badge_map.get(self.plant_condition, "secondary")
