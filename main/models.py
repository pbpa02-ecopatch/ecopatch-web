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
    # Kontak opsional dan pribadi: hanya pemiliknya yang melihat. Dipakai untuk mengisi kolom Kontak di Seed Exchange.
    whatsapp = models.CharField(max_length=15, blank=True, help_text='Angka saja, format internasional tanpa + (6281234567890)')
    instagram = models.CharField(max_length=30, blank=True, help_text='Username tanpa @')

    def __str__(self):
        return f'Profil {self.user}'

    @property
    def whatsapp_display(self):
        """6281234567890 -> +62 812-3456-7890 (nomor Indonesia dikelompokkan, nomor lain apa adanya)."""
        digits = self.whatsapp
        if not digits:
            return ''
        if digits.startswith('62') and len(digits) > 7:
            rest = digits[2:]
            return f'+62 {rest[:3]}-{rest[3:7]}-{rest[7:]}' if len(rest) > 7 else f'+62 {rest[:3]}-{rest[3:]}'
        return f'+{digits}'

    @property
    def whatsapp_url(self):
        return f'https://wa.me/{self.whatsapp}' if self.whatsapp else ''

    @property
    def instagram_url(self):
        return f'https://instagram.com/{self.instagram}' if self.instagram else ''

    def contact_text(self):
        """Satu baris kontak untuk mengisi listing Seed Exchange; kosong kalau belum ada kontak."""
        parts = []
        if self.whatsapp:
            parts.append(f'WhatsApp {self.whatsapp_display}')
        if self.instagram:
            parts.append(f'Instagram @{self.instagram}')
        return ' / '.join(parts)
