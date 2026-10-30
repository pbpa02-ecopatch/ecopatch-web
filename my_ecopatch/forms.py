from django import forms

from plant_library.models import Plant

from .models import EcoPatch, PatchPlant

# What the member sees for each PatchPlant status. The stored values (and the model's English labels) are unchanged.
STATUS_LABELS = {
    'planned': 'Rencana',
    'planted': 'Sudah ditanam',
    'growing': 'Sedang tumbuh',
    'harvested': 'Sudah panen',
    'removed': 'Sudah dicabut',
}


class EcoPatchForm(forms.ModelForm):
    class Meta:
        model = EcoPatch
        fields = ['name', 'space_type', 'size_m2', 'sunlight', 'goal']
        labels = {
            'name': 'Nama EcoPatch',
            'space_type': 'Tipe ruang',
            'size_m2': 'Ukuran ruang (m²)',
            'sunlight': 'Paparan sinar matahari',
            'goal': 'Tujuan berkebun',
        }
        help_texts = {
            'size_m2': 'Opsional.',
            'sunlight': 'Opsional.',
            'goal': 'Opsional.',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Contoh: Balkon Belakang'}),
            'goal': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Contoh: menanam sayur untuk dikonsumsi sendiri'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ganti opsi kosong bawaan Django ("---------") dengan teks yang lebih jelas.
        self.fields['space_type'].choices = [('', 'Pilih tipe ruang')] + list(EcoPatch.SpaceType.choices)
        self.fields['sunlight'].choices = [('', 'Belum ditentukan')] + list(EcoPatch.Sunlight.choices)


class PatchPlantForm(forms.ModelForm):
    class Meta:
        model = PatchPlant
        fields = ['plant', 'quantity', 'status', 'planted_at']
        labels = {
            'plant': 'Tanaman',
            'quantity': 'Jumlah',
            'status': 'Status',
            'planted_at': 'Tanggal mulai menanam',
        }
        help_texts = {'planted_at': 'Opsional.'}
        widgets = {
            'quantity': forms.NumberInput(attrs={'min': 1}),
            'planted_at': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plant'].queryset = Plant.objects.order_by('name')
        self.fields['plant'].empty_label = 'Pilih tanaman'
        self.fields['status'].choices = [(value, STATUS_LABELS.get(value, label)) for value, label in PatchPlant.Status.choices]
