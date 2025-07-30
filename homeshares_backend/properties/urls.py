from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    path('', views.properties_list, name='list'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('owner/', views.owner_console, name='owner_console'),
    path('owner/distribute/<int:pk>/', views.distribute_profits, name='distribute_profits'),

]
