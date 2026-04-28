from __future__ import annotations

import os
import sys

from django.core.management.base import BaseCommand


GUNICORN_ACCESS_LOG_FORMAT = (
    '{"timestamp":"%(t)s","remote_addr":"%(h)s","method":"%(m)s",'
    '"path":"%(U)s","query":"%(q)s","status":%(s)s,"bytes":%(b)s,'
    '"duration_us":%(D)s,"pid":"%(p)s"}'
)


class Command(BaseCommand):
    help = "Запускает production runtime: gunicorn."

    def add_arguments(self, parser):
        parser.add_argument(
            "--bind",
            default=os.getenv("GUNICORN_BIND", "127.0.0.1:8000"),
            help="Адрес и порт для bind gunicorn.",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=int(os.getenv("GUNICORN_WORKERS", "4")),
            help="Количество worker-процессов gunicorn.",
        )
        parser.add_argument(
            "--threads",
            type=int,
            default=int(os.getenv("GUNICORN_THREADS", "2")),
            help="Количество потоков на один worker gunicorn.",
        )
        parser.add_argument(
            "--worker-class",
            default=os.getenv("GUNICORN_WORKER_CLASS", "gthread"),
            help="Класс worker gunicorn.",
        )
        parser.add_argument(
            "--log-level",
            default=os.getenv("GUNICORN_LOG_LEVEL", "info"),
            help="Уровень логирования gunicorn.",
        )
        parser.add_argument(
            "--worker-tmp-dir",
            default=os.getenv("GUNICORN_WORKER_TMP_DIR", "/tmp"),
            help="Временная директория gunicorn worker-процессов.",
        )

    def handle(self, *args, **options):
        gunicorn_args = [
            sys.executable,
            "-m",
            "gunicorn.app.wsgiapp",
            "vizoology.wsgi:application",
            "--bind",
            options["bind"],
            "--workers",
            str(options["workers"]),
            "--threads",
            str(options["threads"]),
            "--worker-class",
            options["worker_class"],
            "--worker-tmp-dir",
            options["worker_tmp_dir"],
            "--access-logfile",
            "-",
            "--access-logformat",
            GUNICORN_ACCESS_LOG_FORMAT,
            "--error-logfile",
            "-",
            "--log-level",
            options["log_level"],
        ]

        self.stdout.write(
            f"Starting Gunicorn on {options['bind']} with workers={options['workers']} threads={options['threads']}..."
        )

        # exec сохраняет PID процесса, что удобно для Docker и signal handling.
        os.execvpe(sys.executable, gunicorn_args, os.environ.copy())
