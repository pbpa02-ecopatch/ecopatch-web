"""
URL configuration for ecopatch_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from main import views as main_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
    path('accounts/', include('allauth.urls')),
    # TODO: masing-masing PIC menambahkan include() untuk app-nya sendiri:
    path('smart-care/', include('smart_care.urls')),
    path('plants/', include('plant_library.urls')),
    path('my-ecopatch/', include('my_ecopatch.urls')),
    path('journal/', include('garden_journal.urls')),
    path('seed-exchange/', include('seed_exchange.urls')),
]

# Uploaded files are served by Django itself (see main.views.media), with DEBUG on or off
urlpatterns += [path(settings.MEDIA_URL.lstrip('/') + '<path:path>', main_views.media, name='media')]
