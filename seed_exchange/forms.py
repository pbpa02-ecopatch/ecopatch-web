from django import forms

from .models import SeedExchange


class SeedExchangeForm(forms.ModelForm):
    """Form create/update listing.

    Field `status` ditampilkan tapi di-create selalu default 'available'.
    Dropdown custom di-render via template (bukan widget Select bawaan),
    jadi `attrs` di sini hanya buat class CSS.
    """

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
        ]  # noqa: RUF012
        labels = {
            'title': 'Judul listing',
            'item_type': 'Jenis item',
            'plant_name': 'Nama tanaman',
            'city': 'Kota',
            'contact': 'Kontak',
            'transaction_type': 'Jenis transaksi',
            'status': 'Status',
            'description': 'Deskripsi',
        }  # noqa: RUF012
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
        }  # noqa: RUF012
