from django import forms

from .models import SeedExchange


class ListingImageField(forms.ImageField):
    """Image field that keeps the current photo when no new file is uploaded."""

    def __init__(self, *args, **kwargs):
        self.existing_image = kwargs.pop('existing_image', False)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # An existing photo satisfies the requirement; only a new upload replaces it.
        # None means "leave the current file untouched" for model file fields.
        if not data and self.existing_image:
            return None
        return super().clean(data, initial)


class SeedExchangeForm(forms.ModelForm):
    """Form create/update listing.

    Field `status` ditampilkan tapi di-create selalu default 'available'.
    Dropdown custom di-render via template (bukan widget Select bawaan),
    jadi `attrs` di sini hanya buat class CSS.
    """

    image = ListingImageField(
        label='Foto listing',
        error_messages={
            'required': 'Foto listing wajib diunggah.',
            'invalid_image': 'File harus berupa gambar (JPG/PNG).',
        },
        widget=forms.FileInput(attrs={
            'class': 'seed-file-input',
            'accept': 'image/*',
        }),
    )

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
            'image',
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
            'image': 'Foto listing',
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

    def __init__(self, *args, create=False, **kwargs):
        super().__init__(*args, **kwargs)
        # A brand new listing always starts "available"; status is managed from
        # the detail page afterwards (so the field is hidden while creating).
        if create:
            self.fields.pop('status')
        # The photo stays required: editing a listing that already has one keeps
        # it unless the owner uploads a replacement.
        self.fields['image'].existing_image = bool(
            self.instance and self.instance.pk and self.instance.image
        )

    def clean_image(self):
        """Reject uploads larger than 5 MB (Django already checks it is an image)."""
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size') and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Ukuran foto maksimal 5 MB.')
        return image
