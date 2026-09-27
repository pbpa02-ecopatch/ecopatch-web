from django import forms

from .models import CareTask


class CareTaskForm(forms.ModelForm):
    # TODO(smart_care): begitu my_ecopatch.PatchPlant tersedia, ganti `city` dengan
    # dropdown patch_plant yang di-filter lewat
    # PatchPlant.objects.filter(ecopatch__user=user) di __init__.
    class Meta:
        model = CareTask
        fields = ["task_type", "city", "due_date", "notes"]
        labels = {
            "task_type": "Jenis tugas",
            "city": "Kota",
            "due_date": "Tanggal",
            "notes": "Catatan",
        }
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Opsional, misalnya: pakai pupuk kompos cair"}),
        }
