from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/clients/', views.clients_list, name='clients-list'),
    path('api/clients/onboard/', views.onboard_client, name='clients-onboard'),
]
