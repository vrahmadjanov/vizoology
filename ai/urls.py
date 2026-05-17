from django.urls import path

from ai import views

urlpatterns = [
    path("", views.ask, name="ask"),
]
