"""config URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from management import views as management_views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='login', permanent=False)),
    path('login/', management_views.login_view, name='login'),
    path('dashboard/', management_views.summary_view, name='dashboard'),
    path('collateral-dynamic/', management_views.collateral_dynamic_view, name='collateral_dynamic'),
    path('collateral-dynamic/static/', management_views.collateral_static_view, name='collateral_static'),
    path('forecast/', management_views.forecast_view, name='forecast'),
    path('risk/', management_views.risk_view, name='risk'),
    path('reports/', management_views.reports_view, name='reports'),
    path(
        'reports/download/<int:report_id>/',
        management_views.reports_download,
        name='reports_download',
    ),
    path(
        'reports/bbc-latest/',
        management_views.reports_generate_bbc,
        name='reports_generate_bbc',
    ),
    path('limits/', management_views.limits_view, name='limits'),
    path('logout/', management_views.logout_view, name='logout'),
    path('admin/', admin.site.urls),
]
