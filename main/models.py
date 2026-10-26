from django.conf import settings
from django.db import models


# Kota yang didukung Smart Care (Open-Meteo) dan Seed Exchange; samakan bila daftar mereka berubah
CITY_CHOICES = [(city, city) for city in (
    'Jakarta', 'Bogor', 'Depok', 'Tangerang', 'Bekasi', 'Bandung',
    'Semarang', 'Yogyakarta', 'Surabaya', 'Malang', 'Medan', 'Makassar',
)]


class Profile(models.Model):
    """Foto dan deskripsi tambahan untuk User bawaan Django (dibuat saat pertama kali dibutuhkan)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True)
    bio = models.TextField(max_length=300, blank=True)
    city = models.CharField(max_length=50, choices=CITY_CHOICES, blank=True)
    # Dipakai ulang sebagai kontak default saat membuat listing Seed Exchange.
    contact = models.CharField(
        max_length=100,
        blank=True,
        help_text='Nomor WA, email, atau akun sosmed yang bisa dihubungi.',
    )

    def __str__(self):
        return f'Profil {self.user}'
