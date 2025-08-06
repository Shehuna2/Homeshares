# myproject/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('properties/', include('properties.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('api/properties/', include('properties.api_urls')),
]