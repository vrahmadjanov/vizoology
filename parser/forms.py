from __future__ import annotations

from django import forms
from django.conf import settings

from ai.validators import validate_min_score_form, validate_top_k_form


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
        label="Top-k",
        validators=[validate_top_k_form],
    )
    min_score = forms.FloatField(
        label="Мин. score",
        validators=[validate_min_score_form],
    )
    save_history = forms.BooleanField(
        required=False,
        initial=True,
        label="Сохранять в историю (QuestionAnswerHistory)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["min_score"].initial = settings.RAG_MIN_SCORE
