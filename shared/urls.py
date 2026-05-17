from django.urls import path

from shared import views

app_name = "shared"

urlpatterns = [
    path("", views.home, name="home"),
]
