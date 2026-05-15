from __future__ import annotations

import uuid

from django.db import models


class ExcelAskJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидание"
        PROCESSING = "processing", "Обработка"
        DONE = "done", "Готово"
        FAILED = "failed", "Ошибка"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    original_filename = models.CharField(max_length=255)
    input_file = models.FileField(upload_to="excel_ask/in/%Y%m%d/")
    result_file = models.FileField(
        upload_to="excel_ask/out/%Y%m%d/", blank=True, max_length=500
    )
    sheet = models.CharField(max_length=255, blank=True)
    questions_col = models.CharField(max_length=10, blank=True)
    answers_start_col = models.CharField(max_length=10, blank=True)
    top_k = models.PositiveIntegerField(default=5)
    min_score = models.FloatField()
    save_history = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.status})"
