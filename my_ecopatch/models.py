from django.conf import settings
from django.core.validators import MinValueValidator
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

    # Daftar kota tetap sesuai README (bagian Open-Meteo): Smart Care mencari koordinat cuaca
    # lewat nama kota ini, jadi nilainya harus persis sama dengan kunci CITY_COORDINATES.
    CITY_CHOICES = [
        ('Jakarta', 'Jakarta'),
        ('Bogor', 'Bogor'),
        ('Depok', 'Depok'),
        ('Tangerang', 'Tangerang'),
        ('Bekasi', 'Bekasi'),
        ('Bandung', 'Bandung'),
        ('Semarang', 'Semarang'),
        ('Yogyakarta', 'Yogyakarta'),
        ('Surabaya', 'Surabaya'),
        ('Malang', 'Malang'),
        ('Medan', 'Medan'),
        ('Makassar', 'Makassar'),
    ]  # noqa: RUF012

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='eco_patches',
    )
    name = models.CharField(max_length=100)
    space_type = models.CharField(max_length=20, choices=SpaceType.choices)
    size_m2 = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1)],
        help_text='Ukuran ruang (m²)',
    )
    sunlight = models.CharField(max_length=20, choices=Sunlight.choices, blank=True)
    city = models.CharField(max_length=50, choices=CITY_CHOICES)
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

    # SEMENTARA: nama tanaman diketik manual karena model Plant di plant_library belum ada.
    # Begitu Plant tersedia, ganti dengan ForeignKey (lihat catatan di jawaban):
    # plant = models.ForeignKey('plant_library.Plant', on_delete=models.PROTECT, related_name='patch_plants')
    plant_name = models.CharField(max_length=100, default='')

    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    planted_at = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.plant_name} @ {self.patch}'
