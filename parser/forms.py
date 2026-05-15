from __future__ import annotations

from django import forms
from django.conf import settings


class ExcelAskForm(forms.Form):
    workbook = forms.FileField(label="Файл Excel (.xlsx)")
    sheet = forms.CharField(
        required=False,
        label="Лист",
        help_text="Пусто — активный лист.",
    )
    questions_col = forms.CharField(
        required=False,
        label="Колонка вопросов",
        max_length=10,
        help_text=f"Буква колонки. Пусто — из настроек (сейчас «{settings.PARSER_DEFAULT_QUESTION_COLUMN_LETTER}»).",
    )
    answers_start_col = forms.CharField(
        required=False,
        label="Первая колонка ответа",
        max_length=10,
        help_text="Пусто — три колонки сразу справа от колонки вопросов.",
    )
    top_k = forms.IntegerField(
        initial=5,
        min_value=1,
        label="Top-k",
    )
    min_score = forms.FloatField(
        min_value=0.0,
        max_value=1.0,
        label="Мин. score",
    )
    save_history = forms.BooleanField(
        required=False,
        initial=True,
        label="Сохранять в историю (QuestionAnswerHistory)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["min_score"].initial = settings.RAG_MIN_SCORE
