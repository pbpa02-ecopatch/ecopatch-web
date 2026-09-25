from django.contrib.auth import logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.shortcuts import redirect, render


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


def logout_view(request):
    logout(request)
    return redirect('main:home')
