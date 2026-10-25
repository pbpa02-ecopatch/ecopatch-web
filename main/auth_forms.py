from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm

User = get_user_model()


class RegisterForm(UserCreationForm):
    """Sign-up form; the email is what "Lupa password" sends the reset link to."""

    email = forms.EmailField(
        max_length=254,
        error_messages={'required': 'Isi email kamu dulu ya.', 'invalid': 'Format email belum benar.'},
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Email ini sudah terdaftar. Coba masuk, atau pakai Lupa password.')
        return email


class EcoPasswordResetForm(PasswordResetForm):
    """Builds the reset link from the host the request came in on, not from django.contrib.sites ("example.com")."""

    def get_users(self, email):
        # Django skips users without a usable password. Here those are people who signed up with Google (or whose
        # password was wiped when Google was linked), and the link in the email is how they get a password of their own.
        return User._default_manager.filter(email__iexact=email, is_active=True)

    def save(self, *args, **kwargs):
        request = kwargs.get('request')
        if request is not None:
            kwargs['domain_override'] = request.get_host()
        return super().save(*args, **kwargs)
