from django import forms
from django.forms import ModelForm

from my_ecopatch.models import EcoPatch
from .models import GardenJournal


class GardenJournalForm(ModelForm):
    ecopatch = forms.ModelChoiceField(
        queryset=EcoPatch.objects.all(),
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_ecopatch"}),
    )

    class Meta:
        model = GardenJournal
        fields = [
            "plant_name",
            "ecopatch",
            "ecopatch_name",
            "date",
            "title",
            "plant_condition",
            "plant_height",
            "image",
            "cover_pattern",
            "cover_color",
            "notes",
        ]
        labels = {
            "plant_name": "Nama Tanaman",
            "ecopatch": "EcoPatch",
            "ecopatch_name": "Nama EcoPatch",
            "plant_height": "Ukuran / Tinggi Tanaman (cm)",
            "image": "Foto Tanaman (Opsional)",
            "cover_pattern": "Pilihan Sampul Buku (Cover Pattern)",
        }
        help_texts = {
            "plant_name": "Isi nama tanaman yang dicatat (misal: Monstera, Tomat Ceri, Cabai Rawit).",
            "ecopatch": "Pilih EcoPatch tempat tanamanmu tumbuh.",
            "ecopatch_name": "Isi nama kebunmu (contoh: Balkon Timur, Kebun Depan).",
            "plant_height": "Tinggi batang, panjang sulur, atau bentang tanaman dalam cm.",
            "image": "Upload foto perkembangan tanaman hari ini (JPG/PNG).",
            "cover_pattern": "Pilih motif cover buku jurnal untuk tanaman ini.",
        }
        widgets = {
            "plant_name": forms.TextInput(
                attrs={"class": "form-control ep-input", "placeholder": "cth: Monstera Deliciosa", "required": "required"}
            ),
            "ecopatch_name": forms.TextInput(
                attrs={"class": "form-control ep-input", "placeholder": "cth: Balkon Timur"}
            ),
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control ep-input"}),
            "title": forms.TextInput(attrs={"class": "form-control ep-input", "placeholder": "cth: Daun baru mulai merekah"}),
            "plant_condition": forms.Select(attrs={"class": "form-select"}),
            "plant_height": forms.NumberInput(
                attrs={"class": "form-control ep-input", "step": "0.1", "min": "0", "placeholder": "cm"}
            ),
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "cover_pattern": forms.RadioSelect(attrs={"class": "cover-radio-input"}),
            "cover_color": forms.HiddenInput(attrs={"id": "id_cover_color"}),
            "notes": forms.Textarea(
                attrs={"rows": 4, "class": "form-control ep-input", "placeholder": "Ada daun baru? Perlu disiram? Tulis apa yang kamu lihat hari ini."}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields["ecopatch"].queryset = EcoPatch.objects.filter(owner=user)
        self.fields["ecopatch"].required = False
        self.fields["ecopatch_name"].required = False

    def clean(self):
        cleaned_data = super().clean()
        ecopatch = cleaned_data.get("ecopatch")
        ecopatch_name = cleaned_data.get("ecopatch_name", "").strip()

        if ecopatch:
            cleaned_data["ecopatch_name"] = ecopatch.name
        elif ecopatch_name and self.user:
            matched = EcoPatch.objects.filter(owner=self.user, name__iexact=ecopatch_name).first()
            if matched:
                cleaned_data["ecopatch"] = matched
                cleaned_data["ecopatch_name"] = matched.name
        return cleaned_data

    def clean_plant_height(self):
        height = self.cleaned_data.get("plant_height")
        if height is not None and height < 0:
            raise forms.ValidationError("Ukuran tanaman tidak boleh negatif.")
        return height
