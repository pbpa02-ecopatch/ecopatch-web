from django.conf import settings
from django.db import models


class SeedExchange(models.Model):
    """Listing berbagi/tukar bibit (modul Seed Exchange).

    Relasi: User -> SeedExchange (owner). Field `plant_name`
    sengaja CharField karena `plant_library.Plant` belum ada modelnya;
    nanti bisa diganti FK tanpa ubah view/filter.
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
    ]  # noqa: RUF012

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seed_listings',
    )
    # Who reserved (null = none). Owner sees requester; requester sees owner contact.
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
    image = models.ImageField(
        upload_to='seed_exchange/',
        blank=False,
        null=True,
        help_text='Foto bibit/tanaman (wajib, JPG/PNG, maks 5 MB)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']  # noqa: RUF012

    def __str__(self):
        return self.title

    @property
    def owner_contact(self):
        """The owner's contact as it is on their profile right now.

        The contact saved with the listing is only a copy (kept in step with the profile), so it
        is the fallback for an owner whose profile no longer has one.
        """
        profile = getattr(self.user, 'profile', None)
        return (profile.contact_text() if profile else '') or self.contact
