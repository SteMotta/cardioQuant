from django.urls import path
from .views import *

app_name = 'calcolatore'
urlpatterns = [
    path('', index, name='index'),
    path('calculate', calculate, name='calculate'),
]