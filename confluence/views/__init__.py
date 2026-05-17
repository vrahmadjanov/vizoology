"""HTTP-представления приложения confluence."""

from confluence.views.indexing_ui import index_documentation_form, index_documentation_job
from confluence.views.search import local_documentation_search

__all__ = [
    "index_documentation_form",
    "index_documentation_job",
    "local_documentation_search",
]
