from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='main/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # allauth ships its own sign-in and sign-up pages; keep ours as the only ones
    path('accounts/login/', RedirectView.as_view(pattern_name='main:login', query_string=True)),
    path('accounts/signup/', RedirectView.as_view(pattern_name='main:register', query_string=True)),

    # same URLs as allauth's Google provider, but answered here first so a missing client id/secret
    # sends people back to the login page instead of raising an error
    path('accounts/google/login/', views.google_login),
    path('accounts/google/login/callback/', views.google_callback),
]
