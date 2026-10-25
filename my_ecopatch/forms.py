from django import forms

from plant_library.models import Plant

from .models import EcoPatch, PatchPlant


class EcoPatchForm(forms.ModelForm):
    class Meta:
        model = EcoPatch
        fields = ['name', 'space_type', 'size_m2', 'sunlight', 'city', 'goal']
        labels = {
            'name': 'Nama EcoPatch',
            'space_type': 'Tipe ruang',
            'size_m2': 'Ukuran ruang (m²)',
            'sunlight': 'Paparan sinar matahari',
            'city': 'Kota',
            'goal': 'Tujuan berkebun',
        }
        help_texts = {
            'city': 'Dipakai Smart Care untuk menampilkan cuaca kotamu.',
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
        self.fields['city'].choices = [('', 'Pilih kota')] + list(EcoPatch.CITY_CHOICES)
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
