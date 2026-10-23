from django.urls import path

from . import views

app_name = "garden_journal"

urlpatterns = [
    path("", views.journal_list, name="list"),
    path("plant/<str:plant_name>/", views.plant_journal_history, name="plant_history"),
    path("create/", views.journal_create, name="create"),
    path("<int:pk>/", views.journal_detail, name="detail"),
    path("<int:pk>/edit/", views.journal_edit, name="edit"),
    path("<int:pk>/delete/", views.journal_delete, name="delete"),
    path("filter/", views.journal_filter_ajax, name="filter_ajax"),
]
