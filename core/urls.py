from django.urls import path

from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.home, name='home'),
    path('api/clients/', views.clients_list, name='clients-list'),
    path('api/clients/onboard/', views.onboard_client, name='clients-onboard'),
]
