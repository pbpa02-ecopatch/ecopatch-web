from django.conf import settings
from django.db import models


class SeedExchange(models.Model):
    """Listing berbagi/tukar bibit milik Rheina (modul Seed Exchange).

    Relasi inti: User -> SeedExchange (owner). Field `plant_name`
    sengaja CharField dulu karena `plant_library.Plant` belum ada
    modelnya; nanti bisa diganti FK tanpa ubah view/filter:
    # plant = models.ForeignKey('plant_library.Plant', on_delete=models.PROTECT, related_name='seed_listings', null=True, blank=True)
    """

    class ItemType(models.TextChoices):
        SEED = 'seed', 'Seed'
        SEEDLING = 'seedling', 'Seedling'
        CUTTING = 'cutting', 'Cutting'
        PLANT = 'plant', 'Plant'

    class TransactionType(models.TextChoices):
        GIVEAWAY = 'giveaway', 'Give Away'
        SWAP = 'swap', 'Swap'

    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        REQUESTED = 'requested', 'Menunggu konfirmasi'
        RESERVED = 'reserved', 'Reserved'
        COMPLETED = 'completed', 'Completed'

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
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seed_listings',
    )
    # Siapa yang me-reserve (null = belum ada yang reserve).
    # Dipakai agar owner tahu siapa yang minat & reserver tahu cara hubungi owner.
    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reserved_listings',
    )
    title = models.CharField(max_length=100)
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    plant_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Nama tanaman (untuk filter Tanaman)',
    )
    city = models.CharField(max_length=50, choices=CITY_CHOICES)
    contact = models.CharField(
        max_length=120,
        default='',
        help_text='Wajib: cara menghubungimu (No. WA / email / sosmed)',
    )
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
