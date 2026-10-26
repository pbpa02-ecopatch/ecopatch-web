from django.urls import path

from . import views

# app_name dipakai header.html (request.resolver_match.app_name) untuk menandai menu aktif.
app_name = 'my_ecopatch'

urlpatterns = [
    path('', views.ecopatch_list, name='list'),
    path('new/', views.ecopatch_create, name='create'),
    path('<int:pk>/', views.ecopatch_detail, name='detail'),
    path('<int:pk>/edit/', views.ecopatch_update, name='update'),
    path('<int:pk>/delete/', views.ecopatch_delete, name='delete'),
    path('<int:pk>/plants/add/', views.patchplant_add, name='plant_add'),
    path('plants/<int:pk>/status/', views.patchplant_set_status, name='plant_status'),
    path('plants/<int:pk>/delete/', views.patchplant_delete, name='plant_delete'),
]
