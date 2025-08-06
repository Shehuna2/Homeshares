# properties/api_urls.py
from django.urls import path
from .api_views import create_property

urlpatterns = [
    path('', create_property, name='api-create-property'),
]
