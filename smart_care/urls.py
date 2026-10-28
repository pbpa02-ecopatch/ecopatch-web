from django.urls import path

from . import views

# Namespace: dipanggil sebagai {% url 'smart_care:list' %} atau reverse("smart_care:list"). Prefix /smart-care/ dipasang
# di ecopatch_project/urls.py. Jenis respons tiap endpoint: HTML = halaman penuh, HTMX = potongan HTML untuk popup,
# JSON = dipanggil fetch() dari smart_care.js.
app_name = "smart_care"

urlpatterns = [
    path("", views.care_task_list, name="list"),  # HTML: halaman utama (cuaca, saran, daftar tugas)
    path("weather/", views.weather, name="weather"),  # JSON: cuaca + saran untuk kota user (GET)
    path("create/", views.care_task_create, name="create"),  # HTML/HTMX: form tambah tugas (GET tampil, POST simpan)
    path("<int:pk>/edit/", views.care_task_update, name="update"),  # HTML/HTMX: form ubah tugas
    path("<int:pk>/delete/", views.care_task_delete, name="delete"),  # POST saja, lalu redirect ke daftar
    path("<int:pk>/complete/", views.care_task_complete, name="complete"),  # JSON: toggle pending <-> completed
    path("suggestions/accept/", views.suggestion_accept, name="suggestion_accept"),  # JSON: terima saran jadi tugas selesai
    path("suggestions/skip/", views.suggestion_skip, name="suggestion_skip"),  # JSON: lewati saran (disimpan sebagai skipped)
    path("suggestions/restore/", views.suggestion_restore, name="suggestion_restore"),  # JSON: batalkan lewati
]
