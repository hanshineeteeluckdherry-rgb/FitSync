from django.urls import path
from . import views

app_name = "activities"

urlpatterns = [
    path("", views.activity_list, name="activity_list"),
    path("add/", views.add_activity, name = "add_activity"),
    path("<int:pk>/", views.activity_detail, name = "activity_detail"),
    path("<int:pk>/delete/", views.delete_activity, name = "delete_activity"),
]