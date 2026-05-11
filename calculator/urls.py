from django.urls import path
from .views import *

app_name = 'calculator'
urlpatterns = [
    path('', index, name='index'),
    path('calculate', calculate, name='calculate'),
    path('calculate/<int:pk>', calculate, name='calculate'),
    path('example', example, name='example'),
    path('calculate_example', calculate_example, name='calculate_example'),
    path('dashboard', dashboard, name='dashboard'),
    path('delete_dataset/<int:pk>', delete_dataset, name='delete_dataset')
]