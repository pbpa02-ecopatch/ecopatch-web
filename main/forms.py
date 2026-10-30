import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm

from .models import CITY_CHOICES, Profile

MAX_AVATAR_BYTES = 2 * 1024 * 1024


class UserForm(forms.ModelForm):
    # Username sengaja tidak ada di sini: dipakai untuk masuk dan tidak bisa diubah dari profil
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'Nama depan',
            'last_name': 'Nama belakang',
            'email': 'Email',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'maxlength': 30, 'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'maxlength': 30, 'autocomplete': 'family-name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Email dipakai untuk reset password, jadi tidak boleh dikosongkan dari profil
        self.fields['email'].required = True
        self.fields['email'].error_messages['required'] = 'Email wajib diisi.'
        self.fields['email'].error_messages['invalid'] = 'Format email belum benar. Contoh: nama@gmail.com'

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if get_user_model().objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Email ini sudah dipakai akun lain.')
        return email


class AvatarForm(forms.ModelForm):
    """Foto profil: unggahan atau salah satu wajah Petak, tidak keduanya."""

    remove_avatar = forms.BooleanField(required=False, label='Hapus foto profil')

    class Meta:
        model = Profile
        fields = ['avatar', 'avatar_petak']
        labels = {'avatar': 'Foto profil'}
        widgets = {
            # disembunyikan: yang terlihat tombol foto di atas profil, yang membuka pemilih file ini
            'avatar': forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp', 'hidden': True}),
            'avatar_petak': forms.HiddenInput(),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        # Hanya file yang baru diunggah yang punya `content_type`; yang lama dibiarkan
        if avatar and hasattr(avatar, 'content_type') and avatar.size > MAX_AVATAR_BYTES:
            raise forms.ValidationError('Ukuran foto maksimal 2 MB.')
        return avatar

    def save(self, commit=True):
        profile = super().save(commit=False)  # avatar_petak sudah terisi dari kiriman form
        if self.files.get('avatar'):
            profile.avatar_petak = ''  # foto baru menggantikan Petak
        elif self.cleaned_data.get('remove_avatar'):
            profile.avatar.delete(save=False)
            profile.avatar_petak = ''
        elif profile.avatar_petak and profile.avatar:
            profile.avatar.delete(save=False)  # memilih Petak menggantikan foto
        if commit:
            profile.save()
        return profile


class BioForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['city', 'bio']
        labels = {
            'city': 'Kota tempat tinggal',
            'bio': 'Deskripsi',
        }
        help_texts = {
            'city': 'Dipakai untuk cuaca di Smart Care dan otomatis terisi di listing Seed Exchange.',
        }
        widgets = {
            'bio': forms.Textarea(attrs={
                'rows': 4,
                'maxlength': 300,
                'placeholder': 'Ceritakan sedikit tentang kebunmu...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['city'].choices = [('', 'Pilih kota')] + list(CITY_CHOICES)


INSTAGRAM_PATTERN = re.compile(r'^[A-Za-z0-9._]{1,30}$')


class ContactForm(forms.ModelForm):
    """WhatsApp dan Instagram, dua-duanya opsional. Isian dirapikan dulu supaya yang tersimpan seragam."""

    # Batas panjang isian lebih longgar dari kolom di database: orang menempelkan "+62 812-3456-7890" atau satu tautan
    # penuh, dan baru setelah dirapikan (clean_*) isinya harus muat di kolomnya.
    whatsapp = forms.CharField(max_length=24, required=False, label='WhatsApp')
    instagram = forms.CharField(max_length=80, required=False, label='Instagram')

    class Meta:
        model = Profile
        fields = ['whatsapp', 'instagram']
        labels = {'whatsapp': 'WhatsApp', 'instagram': 'Instagram'}
        help_texts = {
            'whatsapp': 'Boleh 0812... atau +62 812... Kami rapikan otomatis.',
            'instagram': 'Cukup username-nya, tanpa tautan.',
        }
        widgets = {
            'whatsapp': forms.TextInput(attrs={
                'inputmode': 'tel', 'autocomplete': 'tel',
                'placeholder': '0812 3456 7890', 'maxlength': 24,
            }),
            'instagram': forms.TextInput(attrs={
                'autocomplete': 'off', 'autocapitalize': 'none', 'spellcheck': 'false',
                'placeholder': 'kebunku', 'maxlength': 60,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # tampilkan nomor yang tersimpan dalam bentuk yang enak dibaca (+62 812-3456-7890), bukan angka mentah
        if not self.is_bound and self.instance.whatsapp:
            self.initial['whatsapp'] = self.instance.whatsapp_display

    def clean_whatsapp(self):
        raw = self.cleaned_data.get('whatsapp', '').strip()
        if not raw:
            return ''
        if re.search(r'[^\d\s+()\-.]', raw):
            raise forms.ValidationError('Nomor hanya boleh berisi angka, spasi, tanda + atau -.')
        digits = re.sub(r'\D', '', raw)
        if digits.startswith('00'):
            digits = digits[2:]
        if digits.startswith('0'):
            digits = '62' + digits[1:]
        elif digits.startswith('8'):
            digits = '62' + digits
        if digits.startswith('62'):
            if not 10 <= len(digits) <= 14 or digits[2] != '8':
                raise forms.ValidationError('Nomor Indonesia seharusnya diawali 08 atau +62 8, contoh 0812 3456 7890.')
        elif not 8 <= len(digits) <= 15:
            raise forms.ValidationError('Nomor terlalu pendek atau terlalu panjang.')
        return digits

    def clean_instagram(self):
        raw = self.cleaned_data.get('instagram', '').strip()
        if not raw:
            return ''
        # tempelan tautan atau @username sama-sama diterima
        raw = re.sub(r'^(https?://)?(www\.)?instagram\.com/', '', raw, flags=re.IGNORECASE)
        username = raw.split('?')[0].strip('/').lstrip('@')
        if not INSTAGRAM_PATTERN.match(username) or username.endswith('.') or '..' in username:
            raise forms.ValidationError('Username Instagram hanya boleh huruf, angka, titik, dan garis bawah (maksimal 30).')
        return username.lower()


class ChangePasswordForm(PasswordChangeForm):
    """PasswordChangeForm dengan label Indonesia dan tanpa autofocus (form ini bukan fokus utama halaman)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Password saat ini'
        self.fields['new_password1'].label = 'Password baru'
        self.fields['new_password2'].label = 'Konfirmasi password baru'
        self.fields['old_password'].widget.attrs.pop('autofocus', None)
