from django.urls import path
from . import views

app_name = 'plant_library'

urlpatterns = [
    path('', views.plant_list, name='plant_list'),
    path('add/', views.plant_create, name='plant_create'),
    path('<int:pk>/', views.plant_detail, name='plant_detail'),
    path('<int:pk>/edit/', views.plant_update, name='plant_update'),
    path('<int:pk>/delete/', views.plant_delete, name='plant_delete'),
]
