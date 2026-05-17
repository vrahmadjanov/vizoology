from __future__ import annotations

from django import forms


class DocumentationIndexForm(forms.Form):
    space_keys = forms.CharField(
        label="Ключи пространств (space)",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "cols": 48,
                "placeholder": "например:\nTEAM\ntrouble",
            }
        ),
        help_text="По одному ключу в строке или через запятую.",
    )
    batch_size = forms.IntegerField(
        label="Размер пачки (sync)",
        initial=25,
        min_value=1,
        required=True,
    )
    max_pages = forms.IntegerField(
        label="Лимит страниц (0 = все)",
        initial=0,
        min_value=0,
        required=True,
    )
    max_chars = forms.IntegerField(
        label="Макс. длина чанка",
        initial=1800,
        min_value=200,
        required=True,
    )
    embed_batch_size = forms.IntegerField(
        label="Батч embeddings (пусто = из настроек)",
        required=False,
        min_value=1,
    )
    embed_max_chunks = forms.IntegerField(
        label="Лимит чанков для эмбеддингов (0 = без лимита)",
        initial=0,
        min_value=0,
        required=True,
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

    def clean(self):
        cleaned = super().clean()
        raw = (cleaned.get("space_keys") or "").strip()
        keys: list[str] = []
        for part in raw.replace(",", "\n").splitlines():
            s = part.strip()
            if s:
                keys.append(s)
        if not keys:
            self.add_error("space_keys", "Укажите хотя бы один ключ пространства.")
        else:
            cleaned["space_keys_list"] = keys
        return cleaned
