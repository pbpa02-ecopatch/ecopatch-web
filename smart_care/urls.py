from django.urls import path

from . import views

app_name = "smart_care"

urlpatterns = [
    path("", views.care_task_list, name="list"),
    path("weather/", views.weather, name="weather"),
    path("create/", views.care_task_create, name="create"),
    path("<int:pk>/edit/", views.care_task_update, name="update"),
    path("<int:pk>/delete/", views.care_task_delete, name="delete"),
    path("<int:pk>/complete/", views.care_task_complete, name="complete"),
    path("suggestions/accept/", views.suggestion_accept, name="suggestion_accept"),
    path("suggestions/skip/", views.suggestion_skip, name="suggestion_skip"),
    path("suggestions/restore/", views.suggestion_restore, name="suggestion_restore"),
]
