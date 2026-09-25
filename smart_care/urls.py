from django.urls import path

from . import views

app_name = "smart_care"

urlpatterns = [
    path("", views.care_task_list, name="list"),
    path("create/", views.care_task_create, name="create"),
    path("<int:pk>/", views.care_task_detail, name="detail"),
    path("<int:pk>/edit/", views.care_task_update, name="update"),
    path("<int:pk>/delete/", views.care_task_delete, name="delete"),
    path("<int:pk>/complete/", views.care_task_complete, name="complete"),
]
