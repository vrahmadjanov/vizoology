from __future__ import annotations

from django.core.exceptions import ValidationError

TOP_K_INVALID = "top_k должен быть больше 0."
MIN_SCORE_INVALID = "min_score должен быть от 0 до 1."


def validate_top_k(value: int) -> None:
    if value < 1:
        raise ValueError(TOP_K_INVALID)


def validate_min_score(value: float) -> None:
    if not 0 <= value <= 1:
        raise ValueError(MIN_SCORE_INVALID)


def validate_top_k_form(value: int) -> None:
    try:
        validate_top_k(value)
    except ValueError as exc:
        raise ValidationError(exc.args[0], code="invalid") from exc


def validate_min_score_form(value: float) -> None:
    try:
        validate_min_score(value)
    except ValueError as exc:
        raise ValidationError(exc.args[0], code="invalid") from exc
