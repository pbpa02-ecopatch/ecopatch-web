from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth import views as auth_views
from allauth.account.models import EmailAddress
from django.contrib import messages
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse, reverse_lazy
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme, urlencode

from .auth_forms import EcoPasswordResetForm, RegisterForm


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
