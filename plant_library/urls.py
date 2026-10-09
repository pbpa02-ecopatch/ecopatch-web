from django.urls import path
from . import views

app_name = 'plant_library'

urlpatterns = [
    path('', views.plant_list, name='plant_list'),
    path('<int:pk>/', views.plant_detail, name='plant_detail'),
]

