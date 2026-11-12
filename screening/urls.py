from django.urls import path

from . import views

app_name = "screening"

urlpatterns = [
    
    path("ping/", views.ping, name="ping"),
    path("search/", views.SearchView.as_view(), name="search"),
]
