from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import AvatarForm, BioForm, ChangePasswordForm, DeleteAccountForm, UserForm
from .models import Profile


def home(request):
    return render(request, 'main/home.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('main:home')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created. You can log in now.')
            return redirect('main:login')
    else:
        form = UserCreationForm()

    return render(request, 'main/register.html', {'form': form})


@login_required
def profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)
    user = request.user

    # Tiap section punya form sendiri; field tersembunyi `action` menandai mana yang dikirim
    forms_ctx = {
        'user_form': UserForm(instance=user),
        'avatar_form': AvatarForm(instance=profile_obj),
        'bio_form': BioForm(instance=profile_obj),
        'password_form': ChangePasswordForm(user),
        'delete_form': DeleteAccountForm(user),
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'profile':
            # Foto dan nama satu card, disimpan bersamaan
            forms_ctx['user_form'] = UserForm(request.POST, instance=user)
            forms_ctx['avatar_form'] = AvatarForm(request.POST, request.FILES, instance=profile_obj)
            if forms_ctx['user_form'].is_valid() and forms_ctx['avatar_form'].is_valid():
                forms_ctx['user_form'].save()
                forms_ctx['avatar_form'].save()
                messages.success(request, 'Profil diperbarui.')
                return redirect('main:profile')
        elif action == 'bio':
            forms_ctx['bio_form'] = BioForm(request.POST, instance=profile_obj)
            if forms_ctx['bio_form'].is_valid():
                forms_ctx['bio_form'].save()
                messages.success(request, 'Deskripsi diperbarui.')
                return redirect('main:profile')
        elif action == 'password':
            forms_ctx['password_form'] = ChangePasswordForm(user, request.POST)
            if forms_ctx['password_form'].is_valid():
                user = forms_ctx['password_form'].save()
                update_session_auth_hash(request, user)  # tetap login setelah ganti password
                messages.success(request, 'Password berhasil diubah.')
                return redirect('main:profile')
        elif action == 'delete':
            forms_ctx['delete_form'] = DeleteAccountForm(user, request.POST)
            if forms_ctx['delete_form'].is_valid():
                profile_obj.avatar.delete(save=False)  # hapus file foto dari storage
                logout(request)
                user.delete()  # data milik user di modul lain ikut terhapus (CASCADE)
                messages.success(request, 'Akunmu sudah dihapus. Sampai jumpa lagi!')
                return redirect('main:home')

    return render(request, 'main/profile.html', {
        **forms_ctx,
        'profile': profile_obj,
        # Hitungan read-only dari relasi modul lain (related_name milik masing-masing model)
        'stats': {
            'patches': request.user.eco_patches.count(),
            'journals': request.user.garden_journals.count(),
            'listings': request.user.seed_listings.count(),
        },
    })


def logout_view(request):
    logout(request)
    return redirect('main:home')
