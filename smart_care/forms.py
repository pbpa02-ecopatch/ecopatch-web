from datetime import timedelta

from django import forms
from django.utils import timezone

from my_ecopatch.models import PatchPlant

from .models import CareTask
from .plant_source import link_task, patch_plant_name, user_patch_plants

# A task may be dated up to this many days before or after today. The limit keeps absurd dates (year 1 or 9999) out of
# the database: the list page does date arithmetic around the chosen day and cannot go past the calendar's ends.
DATE_WINDOW_DAYS = 365
NOTES_MAX_LENGTH = 500


class CareTaskForm(forms.ModelForm):
    # The queryset is replaced in __init__ with the signed-in user's own plants. A ModelChoiceField only accepts
    # a value from its queryset, so a posted id of someone else's plant is rejected on the server too.
    patch_plant = forms.ModelChoiceField(
        queryset=PatchPlant.objects.none(),
        label="Tanaman",
        empty_label="Pilih tanaman",
        error_messages={
            "required": "Pilih tanamannya dulu.",
            "invalid_choice": "Tanaman ini tidak tersedia. Pilih dari daftar.",
        },
    )

    class Meta:
        model = CareTask
        # `user`, `plant_name`, `is_outdoor`, `status`, dan `source` sengaja tidak ada di sini. Pemilik diisi di view
        # dari request.user, sedangkan nama dan flag outdoor disalin dari tanaman di save(). Dengan begitu nilai itu
        # tidak bisa dipalsukan lewat body POST.
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
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={
                "rows": 3, "maxlength": NOTES_MAX_LENGTH, "placeholder": "Opsional, misalnya: pakai pupuk kompos cair",
            }),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
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

    def clean_due_date(self):
        # Django memanggil clean_<nama field> setelah validasi bawaan field itu lolos. Tanggal hanya boleh dalam
        # rentang setahun dari hari ini. Tugas lama yang tanggalnya tidak diubah tetap boleh diedit, jadi
        # catatan atau jenisnya bisa dibetulkan tanpa dipaksa mengganti tanggal.
        due = self.cleaned_data["due_date"]
        if self.instance.pk and due == self.instance.due_date:
            return due
        today = timezone.localdate()
        if not today - timedelta(days=DATE_WINDOW_DAYS) <= due <= today + timedelta(days=DATE_WINDOW_DAYS):
            raise forms.ValidationError("Tanggal harus dalam rentang 1 tahun dari hari ini.")
        return due

    def clean_notes(self):
        notes = self.cleaned_data["notes"]
        if len(notes) > NOTES_MAX_LENGTH:
            raise forms.ValidationError(f"Catatan maksimal {NOTES_MAX_LENGTH} karakter.")
        return notes

    def clean(self):
        # Validasi lintas field. Tugas hasil saran dilindungi constraint unik di database (satu saran per tanaman,
        # jenis, dan hari). Kalau diedit sampai kembar dengan saran lain, database menolaknya dengan IntegrityError,
        # yang tampil sebagai halaman 500. Dicek lebih dulu di sini supaya user mendapat pesan di dalam formnya.
        data = super().clean()
        plant = data.get("patch_plant")
        if self.errors or plant is None or self.instance.source != CareTask.Source.SUGGESTED:
            return data
        clash = CareTask.objects.filter(
            user=self.user, patch_plant=plant, task_type=data["task_type"], due_date=data["due_date"],
            source=CareTask.Source.SUGGESTED,
        ).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("Saran yang sama untuk tanaman dan tanggal ini sudah ada.")
        return data

    def save(self, commit=True):
        # commit=False: objek dibuat tapi belum ditulis ke database, supaya snapshot tanaman bisa diisi dulu.
        # Dipanggil dari view create (lalu view mengisi task.user) maupun update.
        task = super().save(commit=False)
        if self.cleaned_data.get("patch_plant"):
            link_task(task, self.cleaned_data["patch_plant"])
        if commit:
            task.save()
        return task
