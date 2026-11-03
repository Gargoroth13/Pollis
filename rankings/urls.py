from django.urls import path

from . import views

app_name = "rankings"
urlpatterns = [
    path("", views.index, name="index"),
    path("data/", views.data, name="data"),
    path("<str:key>/", views.category, name="category"),
]
