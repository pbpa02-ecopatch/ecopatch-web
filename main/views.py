from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode


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

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created. You can log in now.')
            login_url = reverse('main:login')
            next_url = request.GET.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                login_url += '?' + urlencode({'next': next_url})
            return redirect(login_url)
    else:
        form = UserCreationForm()

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
