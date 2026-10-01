from django.conf import settings
from django.db import models


class EcoPatch(models.Model):
    class SpaceType(models.TextChoices):
        BALCONY = 'balcony', 'Balcony'
        INDOOR = 'indoor', 'Indoor'
        TERRACE = 'terrace', 'Terrace'
        ROOFTOP = 'rooftop', 'Rooftop'
        SMALL_YARD = 'small_yard', 'Small Yard'

    class Sunlight(models.TextChoices):
        FULL = 'full', 'Full Sun'
        PARTIAL = 'partial', 'Partial Sun'
        SHADE = 'shade', 'Shade'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='eco_patches',
    )
    name = models.CharField(max_length=100)
    space_type = models.CharField(max_length=20, choices=SpaceType.choices)
    size_m2 = models.PositiveIntegerField(null=True, blank=True, help_text='Ukuran ruang (m²)')
    sunlight = models.CharField(max_length=20, choices=Sunlight.choices, blank=True)
    city = models.CharField(max_length=100)
    goal = models.TextField(blank=True, help_text='Tujuan berkebun')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class PatchPlant(models.Model):
    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planned'
        PLANTED = 'planted', 'Planted'
        GROWING = 'growing', 'Growing'
        HARVESTED = 'harvested', 'Harvested'
        REMOVED = 'removed', 'Removed'

    patch = models.ForeignKey(EcoPatch, on_delete=models.CASCADE, related_name='plants')
    # belum diintegrasi plant_library
    # plant = models.ForeignKey('plant_library.Plant', on_delete=models.PROTECT, related_name='patch_plants')
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    planted_at = models.DateField(null=True, blank=True)

    def __str__(self):
        return f'{self.patch} - {self.get_status_display()}'
