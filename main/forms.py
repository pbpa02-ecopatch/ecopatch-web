from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm

from .models import Profile

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


class AvatarForm(forms.ModelForm):
    remove_avatar = forms.BooleanField(required=False, label='Hapus foto profil')

    class Meta:
        model = Profile
        fields = ['avatar']
        labels = {'avatar': 'Foto profil'}
        widgets = {'avatar': forms.FileInput(attrs={'accept': 'image/*'})}

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        # Hanya file yang baru diunggah yang punya `content_type`; yang lama dibiarkan
        if avatar and hasattr(avatar, 'content_type') and avatar.size > MAX_AVATAR_BYTES:
            raise forms.ValidationError('Ukuran foto maksimal 2 MB.')
        return avatar

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.cleaned_data.get('remove_avatar') and not self.files.get('avatar'):
            profile.avatar.delete(save=False)
        if commit:
            profile.save()
        return profile


class BioForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['city', 'contact', 'bio']
        labels = {
            'city': 'Kota tempat tinggal',
            'contact': 'Kontak yang bisa dihubungi',
            'bio': 'Deskripsi',
        }
        help_texts = {
            'city': 'Dipakai untuk cuaca di Smart Care dan otomatis terisi di listing Seed Exchange.',
            'contact': 'Otomatis dipakai sebagai kontak di listing Seed Exchange.',
        }
        widgets = {
            'contact': forms.TextInput(attrs={
                'placeholder': 'cth: 0812-3456-7890 / nama@email.com',
            }),
            'bio': forms.Textarea(attrs={
                'rows': 4,
                'maxlength': 300,
                'placeholder': 'Ceritakan sedikit tentang kebunmu...',
            }),
        }


class ChangePasswordForm(PasswordChangeForm):
    """PasswordChangeForm dengan label Indonesia dan tanpa autofocus (form ini bukan fokus utama halaman)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Password saat ini'
        self.fields['new_password1'].label = 'Password baru'
        self.fields['new_password2'].label = 'Konfirmasi password baru'
        self.fields['old_password'].widget.attrs.pop('autofocus', None)


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data['password']
        if not self.user.check_password(password):
            raise forms.ValidationError('Password salah.')
        return password
