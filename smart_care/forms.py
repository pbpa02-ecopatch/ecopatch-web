from django import forms

from .models import CareTask


class CareTaskForm(forms.ModelForm):
    class Meta:
        model = CareTask
        fields = ["plant_name", "task_type", "due_date", "is_outdoor", "notes"]
        labels = {
            "plant_name": "Nama tanaman",
            "task_type": "Jenis tugas",
            "due_date": "Tanggal",
            "is_outdoor": "Tanaman di luar ruangan",
            "notes": "Catatan",
        }
        help_texts = {
            "is_outdoor": "Tanaman dalam ruangan tidak mendapat saran soal hujan.",
        }
        widgets = {
            "plant_name": forms.TextInput(attrs={"placeholder": "Contoh: Cabai rawit"}),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Opsional, misalnya: pakai pupuk kompos cair"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Placeholder yang jelas menggantikan "---------" bawaan Django
        self.fields["task_type"].choices = [("", "Pilih jenis tugas"), *CareTask.TaskType.choices]
