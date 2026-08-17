from django.urls import path

from . import views

urlpatterns = [
    path("trabalhar/", views.trabalhar, name="trabalhar"),
]
