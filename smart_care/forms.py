from django import forms

from my_ecopatch.models import PatchPlant

from .models import CareTask
from .plant_source import link_task, patch_plant_name, user_patch_plants


class CareTaskForm(forms.ModelForm):
    # The queryset is replaced in __init__ with the signed-in user's own plants. A ModelChoiceField only accepts
    # a value from its queryset, so a posted id of someone else's plant is rejected on the server too.
    patch_plant = forms.ModelChoiceField(
        queryset=PatchPlant.objects.none(),
        label="Tanaman",
        empty_label="Pilih tanaman",
        widget=forms.Select(attrs={"class": "ep-input"}),
        error_messages={
            "required": "Pilih tanamannya dulu.",
            "invalid_choice": "Tanaman ini tidak tersedia. Pilih dari daftar.",
        },
    )

    class Meta:
        model = CareTask
        fields = ["patch_plant", "task_type", "due_date", "notes"]
        labels = {
            "task_type": "Jenis tugas",
            "due_date": "Tanggal",
            "notes": "Catatan",
        }
        error_messages = {
            "task_type": {"required": "Pilih jenis tugasnya dulu.", "invalid_choice": "Jenis tugas ini tidak tersedia."},
            "due_date": {"required": "Isi tanggalnya dulu.", "invalid": "Tanggalnya belum benar."},
        }
        widgets = {
            "task_type": forms.Select(attrs={"class": "ep-input"}),
            "due_date": forms.DateInput(attrs={"type": "date", "class": "ep-input"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "ep-input", "placeholder": "Opsional, misalnya: pakai pupuk kompos cair"}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        linked = self.instance.patch_plant_id
        field = self.fields["patch_plant"]
        # The plant of the task being edited stays selectable even if its status in My EcoPatch has moved on
        field.queryset = user_patch_plants(user, keep=linked)
        field.label_from_instance = lambda plant: f"{patch_plant_name(plant)} ({plant.patch.name})"
        # A task made before Smart Care read My EcoPatch has no plant; it can still be edited as it is
        field.required = not (self.instance.pk and not linked)
        self.has_plants = field.queryset.exists()
        # Placeholder yang jelas menggantikan "---------" bawaan Django
        self.fields["task_type"].choices = [("", "Pilih jenis tugas"), *CareTask.TaskType.choices]

    def save(self, commit=True):
        task = super().save(commit=False)
        if self.cleaned_data.get("patch_plant"):
            link_task(task, self.cleaned_data["patch_plant"])
        if commit:
            task.save()
        return task
