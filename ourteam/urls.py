from django.urls import path
from . import views

app_name = "ourteam"

urlpatterns = [
    
    path("", views.ourteam, name="index"),
]