from __future__ import annotations

from django import forms


class DocumentationIndexForm(forms.Form):
    space_keys = forms.MultipleChoiceField(
        label="Пространства (space)",
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Отметьте пространства, которые нужно проиндексировать.",
    )
    batch_size = forms.IntegerField(
        label="Размер пачки (sync)",
        initial=25,
        min_value=1,
        required=True,
    )
    max_chars = forms.IntegerField(
        label="Макс. длина чанка",
        initial=1800,
        min_value=200,
        required=True,
    )
    embed_batch_size = forms.IntegerField(
        label="Пачка векторизации чанков",
        required=False,
        min_value=1,
    )
    dry_run_chunks = forms.BooleanField(
        label="Только посчитасть чанки (dry run)",
        required=False,
        initial=False,
    )
    force_embed = forms.BooleanField(
        label="Пересчитать все эмбеддинги",
        required=False,
        initial=False,
    )

    def __init__(self, *args, space_choices: list[tuple[str, str]] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["space_keys"].choices = space_choices or []

    def clean(self):
        cleaned = super().clean()
        keys = list(cleaned.get("space_keys") or [])
        if not keys:
            self.add_error("space_keys", "Выберите хотя бы одно пространство.")
        else:
            cleaned["space_keys_list"] = keys
        return cleaned
