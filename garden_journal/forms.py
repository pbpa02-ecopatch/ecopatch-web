from django import forms
from django.forms import ModelForm

from .models import GardenJournal


class GardenJournalForm(ModelForm):
    class Meta:
        model = GardenJournal
        fields = [
            "plant_name",
            "ecopatch_name",
            "date",
            "title",
            "plant_condition",
            "plant_height",
            "cover_pattern",
            "notes",
        ]
        labels = {
            "plant_name": "Nama Tanaman",
            "ecopatch_name": "Nama EcoPatch",
            "cover_pattern": "Pilihan Sampul Buku (Cover Pattern)",
        }
        help_texts = {
            "plant_name": "Isi nama tanaman yang dicatat (misal: Monstera, Tomat Ceri, Cabai Rawit).",
            "ecopatch_name": "Isi nama kebunmu (contoh: Balkon Timur, Kebun Depan).",
            "cover_pattern": "Pilih motif cover buku jurnal untuk tanaman ini.",
        }
        widgets = {
            "plant_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "cth: Monstera Deliciosa", "required": "required"}
            ),
            "ecopatch_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "cth: Balkon Timur"}
            ),
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "cth: Daun baru mulai merekah"}),
            "plant_condition": forms.Select(attrs={"class": "form-select"}),
            "plant_height": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.1", "min": "0", "placeholder": "cm"}
            ),
            "cover_pattern": forms.RadioSelect(attrs={"class": "cover-radio-input"}),
            "notes": forms.Textarea(
                attrs={"rows": 4, "class": "form-control", "placeholder": "Tulis perkembangan tanaman hari ini..."}
            ),
        }

    def clean_plant_height(self):
        height = self.cleaned_data.get("plant_height")
        if height is not None and height < 0:
            raise forms.ValidationError("Tinggi tanaman tidak boleh negatif.")
        return height
