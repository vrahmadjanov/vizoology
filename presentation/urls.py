from django.urls import path
from django.views.generic import RedirectView

from presentation import views

urlpatterns = [
    path("ask/", views.excel_ask_view, name="presentation_ask"),
    path(
        "ask/jobs/history/",
        views.excel_ask_job_list_view,
        name="presentation_excel_job_history",
    ),
    path(
        "ask/jobs/",
        RedirectView.as_view(pattern_name="presentation_ask", permanent=False),
        name="presentation_ask_jobs",
    ),
    path(
        "ask/jobs/<uuid:pk>/",
        views.excel_ask_job_view,
        name="presentation_ask_job",
    ),
    path(
        "ask/jobs/<uuid:pk>/status.json",
        views.excel_ask_job_status_json,
        name="presentation_ask_job_status",
    ),
    path(
        "ask/jobs/<uuid:pk>/download/",
        views.excel_ask_job_download_view,
        name="presentation_ask_job_download",
    ),
]
