from django import forms
from .models import Plant


class PlantForm(forms.ModelForm):
    # Django's default "---------" reads like a broken dropdown; give each one a cue.
    EMPTY_LABELS = {
        'category': 'Pilih kategori',
        'sunlight': 'Pilih cahaya',
        'watering': 'Pilih frekuensi',
        'difficulty': 'Pilih kesulitan',
        'indoor_outdoor': 'Pilih penempatan',
        'space_requirement': 'Pilih kebutuhan ruang',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, label in self.EMPTY_LABELS.items():
            field = self.fields[name]
            choices = list(field.choices)
            if choices and choices[0][0] == '':
                choices[0] = ('', label)
            field.choices = choices

    class Meta:
        model = Plant
        fields = [
            'name',
            'scientific_name',
            'category',
            'sunlight',
            'watering',
            'difficulty',
            'indoor_outdoor',
            'space_requirement',
            'description',
            'image_url',
        ]
        labels = {
            'name': 'Nama Tanaman',
            'scientific_name': 'Nama Ilmiah (Latin)',
            'category': 'Kategori Tanaman',
            'sunlight': 'Kebutuhan Sinar Matahari',
            'watering': 'Frekuensi Penyiraman',
            'difficulty': 'Tingkat Kesulitan',
            'indoor_outdoor': 'Penempatan',
            'space_requirement': 'Kebutuhan Ruang / Wadah',
            'description': 'Deskripsi & Panduan Perawatan',
            'image_url': 'URL Gambar Tanaman (Opsional)',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: Lidah Buaya, Tomat Ceri, Basil',
                'required': 'required',
            }),
            'scientific_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: Aloe vera, Solanum lycopersicum',
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'sunlight': forms.Select(attrs={'class': 'form-select'}),
            'watering': forms.Select(attrs={'class': 'form-select'}),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
            'indoor_outdoor': forms.Select(attrs={'class': 'form-select'}),
            'space_requirement': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Tuliskan deskripsi tanaman, media tanam, atau tips perawatannya...',
            }),
            'image_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/gambar-tanaman.jpg',
            }),
        }

