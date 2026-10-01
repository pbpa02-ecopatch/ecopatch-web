from django import forms

from .models import SeedExchange


class SeedExchangeForm(forms.ModelForm):
    class Meta:
        model = SeedExchange
        fields = [
            'title',
            'item_type',
            'plant_name',
            'city',
            'contact',
            'transaction_type',
            'status',
            'description',
        ]
        labels = {
            'title': 'Judul listing',
            'item_type': 'Jenis item',
            'plant_name': 'Nama tanaman',
            'city': 'Kota',
            'contact': 'Kontak',
            'transaction_type': 'Jenis transaksi',
            'status': 'Status',
            'description': 'Deskripsi',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control seed-input',
                'placeholder': 'cth: Bibit Cabai Rawit',
            }),
            'item_type': forms.Select(attrs={'class': 'form-select seed-input'}),
            'plant_name': forms.TextInput(attrs={
                'class': 'form-control seed-input',
                'placeholder': 'cth: Cabai Rawit',
            }),
            'city': forms.Select(attrs={'class': 'form-select seed-input'}),
            'contact': forms.TextInput(attrs={
                'class': 'form-control seed-input',
                'placeholder': 'cth: 0812-3456-7890 / nama@email.com',
            }),
            'transaction_type': forms.Select(attrs={'class': 'form-select seed-input'}),
            'status': forms.Select(attrs={'class': 'form-select seed-input'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control seed-input',
                'rows': 4,
                'placeholder': 'Ceritakan kondisi bibit/tanaman, jumlah, cara ambil/tukar...',
            }),
        }
