from __future__ import annotations

from django import forms
from django.conf import settings

from ai.validators import validate_min_score_form, validate_top_k_form


class ExcelAskForm(forms.Form):
    workbook = forms.FileField(
        label="Файл Excel (.xlsx)",
        widget=forms.FileInput(
            attrs={
                "accept": ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "class": "drop-zone-input",
            }
        ),
    )
    sheet = forms.CharField(
        required=False,
        label="Лист",
    )
    questions_col = forms.CharField(
        required=False,
        label="Колонка вопросов",
        max_length=10,
        widget=forms.TextInput(attrs={"placeholder": "Q"}),
    )
    answers_start_col = forms.CharField(
        required=False,
        label="Первая колонка ответа",
        max_length=10,
        widget=forms.TextInput(attrs={"placeholder": "R"}),
    )
    top_k = forms.IntegerField(
        initial=5,
        label="Топ источников",
        validators=[validate_top_k_form],
    )
    min_score = forms.FloatField(
        label="Мин. точность",
        validators=[validate_min_score_form],
    )
    save_history = forms.BooleanField(
        required=False,
        initial=True,
        label="Сохранить в историю",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["min_score"].initial = settings.RAG_MIN_SCORE
