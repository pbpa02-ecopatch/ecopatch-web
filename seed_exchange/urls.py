from django.urls import path

from . import views

app_name = 'seed_exchange'

urlpatterns = [
    path('', views.listing_list, name='list'),
    path('create/', views.listing_create, name='create'),
    path('<int:pk>/', views.listing_detail, name='detail'),
    path('<int:pk>/edit/', views.listing_update, name='update'),
    path('<int:pk>/delete/', views.listing_delete, name='delete'),
    path('<int:pk>/reserve/', views.listing_reserve, name='reserve'),
    path('<int:pk>/accept/', views.listing_accept, name='accept'),
    path('<int:pk>/cancel-reserve/', views.listing_cancel_reserve, name='cancel_reserve'),
    path('<int:pk>/complete/', views.listing_complete, name='complete'),
    path('<int:pk>/reopen/', views.listing_reopen, name='reopen'),
]
