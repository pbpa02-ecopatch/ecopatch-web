from django.urls import path

from . import views

app_name = 'my_ecopatch'

urlpatterns = [
    path('', views.ecopatch_list, name='list'),
]
