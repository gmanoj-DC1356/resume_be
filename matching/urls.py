from django.urls import path

from . import views

app_name = "matching"

urlpatterns = [
    path("ping/", views.ping, name="ping"),  # placeholder - replace with real endpoints
    path("sessions/", views.SessionHistoryView.as_view(), name="sessions"),
    path("sessions/<int:pk>/", views.SessionDetailView.as_view(), name="session-detail"),
]
