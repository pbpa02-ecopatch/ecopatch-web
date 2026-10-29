from django.db.models.signals import post_delete
from django.dispatch import receiver
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
        ("bark", "Bark"),
        ("terra", "Terra"),
        ("moss", "Moss"),
        ("clay", "Clay"),
        ("pebbles", "Pebbles"),
        ("polkadot", "Polkadot"),
        ("solid", "Solid Color"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="garden_journals")
    ecopatch = models.ForeignKey(
        "my_ecopatch.EcoPatch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="journals",
        help_text="Relasi ke EcoPatch milik user",
    )
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
    cover_color = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Warna hex untuk sampul polos (misal: #1f9142)",
    )
    image = models.ImageField(
        upload_to="journal_photos/",
        blank=True,
        null=True,
        help_text="Foto tanaman (opsional)",
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

    @property
    def get_condition_ds_class(self):
        """Mapping status condition ke kelas badge Design System (badge-ds-*)."""
        ds_map = {
            "healthy": "badge-ds-healthy",
            "needs_attention": "badge-ds-attention",
            "wilting": "badge-ds-wilting",
            "flowering": "badge-ds-flowering",
            "fruiting": "badge-ds-planned",
            "ready_to_harvest": "badge-ds-healthy",
        }
        return ds_map.get(self.plant_condition, "badge-ds-attention")

    def save(self, *args, **kwargs):
        if self.ecopatch and not self.ecopatch_name:
            self.ecopatch_name = self.ecopatch.name
        elif self.ecopatch and self.ecopatch_name != self.ecopatch.name:
            self.ecopatch_name = self.ecopatch.name
        elif not self.ecopatch and self.ecopatch_name and self.user_id:
            from my_ecopatch.models import EcoPatch
            patch = EcoPatch.objects.filter(owner_id=self.user_id, name__iexact=self.ecopatch_name.strip()).first()
            if patch:
                self.ecopatch = patch
        super().save(*args, **kwargs)


@receiver(post_delete, sender=GardenJournal)
def auto_delete_journal_photo_on_delete(sender, instance, **kwargs):
    if instance.image:
        instance.image.delete(save=False)
