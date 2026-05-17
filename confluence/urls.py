from django.urls import path

from confluence.views import (
    index_documentation_form,
    index_documentation_job,
    local_documentation_search,
)

app_name = "confluence"

urlpatterns = [
    path("index/", index_documentation_form, name="index_documentation_ui"),
    path(
        "index/<uuid:job_id>/",
        index_documentation_job,
        name="index_documentation_job",
    ),
    path("search/", local_documentation_search, name="documentation_search"),
]
