from django.db import models


class QuestionAnswerHistory(models.Model):
    question = models.TextField()
    short_answer = models.TextField()
    reasoning_summary = models.TextField(blank=True)
    source_numbers = models.JSONField(default=list, blank=True)
    sources = models.JSONField(default=list, blank=True)
    model_name = models.CharField(max_length=255, blank=True, db_index=True)
    top_k = models.PositiveIntegerField(default=5)
    min_score = models.FloatField(default=0.55)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["model_name", "created_at"]),
        ]

    def __str__(self) -> str:
        return self.question[:100]
