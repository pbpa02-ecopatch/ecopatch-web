from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),

    # "Lupa password": ask for the email, send a link, choose a new password
    path('lupa-password/', views.PasswordResetView.as_view(), name='password_reset'),
    path('lupa-password/terkirim/', views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('lupa-password/<uidb64>/<token>/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('lupa-password/selesai/', views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # allauth ships its own sign-in and sign-up pages; keep ours as the only ones
    path('accounts/login/', RedirectView.as_view(pattern_name='main:login', query_string=True)),
    path('accounts/signup/', RedirectView.as_view(pattern_name='main:register', query_string=True)),

    # same URLs as allauth's Google provider, but answered here first so a missing client id/secret
    # sends people back to the login page instead of raising an error
    path('accounts/google/login/', views.google_login),
    path('accounts/google/login/callback/', views.google_callback),
]
