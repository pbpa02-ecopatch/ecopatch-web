import hashlib

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from allauth.account.models import EmailAddress
from django.contrib import messages
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse, reverse_lazy
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.static import serve
from django.views.decorators.http import require_POST

from .auth_forms import EcoPasswordResetForm, RegisterForm

from .forms import AvatarForm, BioForm, ChangePasswordForm, ContactForm, UserForm
from .models import PETAK_CHOICES, Profile


# Guessing passwords: after this many wrong tries for one username from one address the login pauses for a while.
LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_SECONDS = 5 * 60


def _login_key(request, username):
    who = f"{request.META.get('REMOTE_ADDR', '')}|{username.strip().lower()}"
    return 'login-failures:' + hashlib.sha256(who.encode()).hexdigest()


class LoginView(auth_views.LoginView):
    template_name = 'main/login.html'
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if cache.get(_login_key(request, request.POST.get('username', '')), 0) >= LOGIN_MAX_FAILURES:
            # an empty form: while locked, not even a correct password is tried
            form = self.get_form_class()(request=request)
            form.cleaned_data = {}
            form.add_error(None, 'Terlalu banyak percobaan masuk. Tunggu beberapa menit, lalu coba lagi.')
            return self.render_to_response(self.get_context_data(form=form, locked=True), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = _login_key(self.request, self.request.POST.get('username', ''))
        cache.add(key, 0, LOGIN_LOCK_SECONDS)
        try:
            cache.incr(key)
        except ValueError:  # the entry expired between add and incr
            cache.set(key, 1, LOGIN_LOCK_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(_login_key(self.request, self.request.POST.get('username', '')))
        return super().form_valid(form)


def media(request, path):
    """Serve uploaded files (profile photos, listing and journal photos), also when DEBUG is off.

    WhiteNoise only serves static files and `static()` only works while DEBUG is on, so on a server such as
    PWS every upload would 404. `serve` refuses paths that climb out of MEDIA_ROOT. MEDIA_ROOT is read on each
    request, so a test can point it at a temporary folder.
    """
    return serve(request, path, document_root=settings.MEDIA_ROOT)


def home(request):
    # The landing page is for guests; people who are signed in have no use for it
    if request.user.is_authenticated:
        return redirect('my_ecopatch:list')

    # The Plant Library route is added by another module; until it exists the landing links to its own anchor.
    try:
        plant_library_url = reverse('plant_library:plant_list')
    except NoReverseMatch:
        plant_library_url = ''
    return render(request, 'main/home.html', {'plant_library_url': plant_library_url})


def register(request):
    if request.user.is_authenticated:
        return redirect('my_ecopatch:list')

    # Django's own validation messages, in Indonesian, only for this page
    with translation.override('id'):
        if request.method == 'POST':
            form = RegisterForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Akun berhasil dibuat. Silakan masuk.')
                login_url = reverse('main:login')
                next_url = request.GET.get('next', '')
                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                    login_url += '?' + urlencode({'next': next_url})
                return redirect(login_url)
        else:
            form = RegisterForm()

        return render(request, 'main/register.html', {'form': form})


@login_required
def profile(request):
    # Aturan dan pesan password bawaan Django, dalam bahasa Indonesia (seperti halaman daftar)
    with translation.override('id'):
        return _profile(request)


def _profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)
    user = request.user

    # Satu form besar (foto, nama, kota, deskripsi, kontak) dengan satu tombol Simpan; field tersembunyi `action`
    # menandai bagian mana yang dikirim. Password tetap form terpisah di dalam dialognya.
    forms_ctx = {
        'user_form': UserForm(instance=user),
        'avatar_form': AvatarForm(instance=profile_obj),
        'bio_form': BioForm(instance=profile_obj),
        'contact_form': ContactForm(instance=profile_obj),
        'password_form': ChangePasswordForm(user),
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save':
            forms_ctx['user_form'] = UserForm(request.POST, instance=user)
            forms_ctx['avatar_form'] = AvatarForm(request.POST, request.FILES, instance=profile_obj)
            forms_ctx['bio_form'] = BioForm(request.POST, instance=profile_obj)
            forms_ctx['contact_form'] = ContactForm(request.POST, instance=profile_obj)
            sections = [forms_ctx[name] for name in ('user_form', 'avatar_form', 'bio_form', 'contact_form')]
            # Semuanya valid atau tidak ada yang disimpan, supaya satu kolom salah tidak menyimpan sebagian
            if all([form.is_valid() for form in sections]):
                for form in sections:
                    form.save()
                messages.success(request, 'Profil disimpan.')
                return redirect('main:profile')
        elif action == 'password':
            forms_ctx['password_form'] = ChangePasswordForm(user, request.POST)
            if forms_ctx['password_form'].is_valid():
                user = forms_ctx['password_form'].save()
                update_session_auth_hash(request, user)  # tetap login setelah ganti password
                messages.success(request, 'Password berhasil diubah.')
                return redirect('main:profile')

    steps = profile_obj.completeness()
    return render(request, 'main/profile.html', {
        **forms_ctx,
        'profile': profile_obj,
        'petak_choices': PETAK_CHOICES,
        'steps': steps,
        'steps_done': sum(1 for _, done, _ in steps if done),
        'next_step': next((step for step in steps if not step[1]), None),
        # Hitungan read-only dari relasi modul lain (related_name milik masing-masing model)
        'stats': {
            'patches': request.user.eco_patches.count(),
            'journals': request.user.garden_journals.count(),
            'listings': request.user.seed_listings.count(),
        },
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect('main:home')


def google_unavailable(request):
    messages.info(request, 'Masuk dengan Google belum diaktifkan. Silakan masuk dengan username dan password.')
    return redirect('main:login')


def google_login(request):
    if not settings.GOOGLE_AUTH_ENABLED:
        return google_unavailable(request)
    from allauth.socialaccount.providers.google.views import oauth2_login
    return oauth2_login(request)


def google_callback(request):
    if not settings.GOOGLE_AUTH_ENABLED:
        return google_unavailable(request)
    from allauth.socialaccount.providers.google.views import oauth2_callback
    return oauth2_callback(request)


class IndonesianMixin:
    """Django's own messages (validators, form errors) in Indonesian, for the password reset pages only."""

    def dispatch(self, request, *args, **kwargs):
        with translation.override('id'):
            response = super().dispatch(request, *args, **kwargs)
            if hasattr(response, 'render') and not response.is_rendered:
                response.render()  # TemplateResponse renders lazily, so do it while Indonesian is active
        return response


class PasswordResetView(IndonesianMixin, auth_views.PasswordResetView):
    template_name = 'main/password_reset_form.html'
    email_template_name = 'main/emails/password_reset_email.txt'
    subject_template_name = 'main/emails/password_reset_subject.txt'
    form_class = EcoPasswordResetForm
    success_url = reverse_lazy('main:password_reset_done')


class PasswordResetDoneView(IndonesianMixin, auth_views.PasswordResetDoneView):
    template_name = 'main/password_reset_done.html'


class PasswordResetConfirmView(IndonesianMixin, auth_views.PasswordResetConfirmView):
    template_name = 'main/password_reset_confirm.html'
    success_url = reverse_lazy('main:password_reset_complete')

    def form_valid(self, form):
        response = super().form_valid(form)
        # the reset link only reaches the owner of the email, so using it proves the email is theirs
        user = self.user
        if user.email:
            address = EmailAddress.objects.filter(user=user, email__iexact=user.email).first()
            try:
                if address:
                    address.verified = True
                    address.save(update_fields=['verified'])
                else:
                    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
            except IntegrityError:
                pass  # the same address is already verified on another account; leave it alone
        return response


class PasswordResetCompleteView(IndonesianMixin, auth_views.PasswordResetCompleteView):
    template_name = 'main/password_reset_complete.html'
