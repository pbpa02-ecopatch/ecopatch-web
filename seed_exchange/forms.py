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

    Field `status` hanya muncul saat edit, dan hanya selama tidak ada yang
    sedang minta/booking listing-nya (lihat `__init__`); di create selalu 'available'.
    Dropdown custom di-render via template (bukan widget Select bawaan),
    jadi `attrs` di sini hanya buat class CSS.
    """

    # What the owner may pick by hand once nobody holds the listing; the
    # requested -> reserved -> completed steps belong to the booking buttons.
    MANUAL_STATUSES = (SeedExchange.Status.AVAILABLE, SeedExchange.Status.COMPLETED)

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
            'transaction_type',
            'status',
            'description',
            'image',
        ]  # noqa: RUF012
        labels = {
            'title': 'Judul listing',
            'item_type': 'Jenis item',
            'plant_name': 'Nama tanaman',
            'transaction_type': 'Jenis transaksi',
            'status': 'Status',
            'description': 'Deskripsi',
            'image': 'Foto listing',
        }  # noqa: RUF012
        error_messages = {
            'title': {'required': 'Judul listing wajib diisi.'},
            'item_type': {'required': 'Pilih jenis item.'},
            'transaction_type': {'required': 'Pilih jenis transaksi.'},
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
            'transaction_type': forms.Select(attrs={'class': 'form-select seed-input'}),
            'status': forms.Select(attrs={'class': 'form-select seed-input'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control seed-input',
                'rows': 4,
                'placeholder': 'Ceritakan kondisi bibit/tanaman, jumlah, cara ambil/tukar...',
            }),
        }  # noqa: RUF012

    def __init__(self, *args, create=False, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        # City and contact are not asked here: they live on the profile and are copied onto the
        # listing when it is saved (see clean/save), so nobody types them twice or posts their own.
        self.profile = profile
        # A brand new listing always starts "available". Afterwards, while someone has
        # requested or booked it, the status moves only through the booking buttons on the
        # detail page: picking it here would leave reserved_by out of step (a listing
        # "reserved" for nobody, or "available" while a requester still holds it).
        held = bool(self.instance.pk) and (
            self.instance.reserved_by_id is not None
            or self.instance.status not in self.MANUAL_STATUSES
        )
        if create or held:
            self.fields.pop('status')
        else:
            self.fields['status'].choices = [
                choice for choice in SeedExchange.Status.choices if choice[0] in self.MANUAL_STATUSES
            ]
        # The photo stays required: editing a listing that already has one keeps
        # it unless the owner uploads a replacement.
        self.fields['image'].existing_image = bool(
            self.instance and self.instance.pk and self.instance.image
        )

    def _location(self):
        """City and contact the listing will carry: the profile's, with the listing's old value as the fallback."""
        city = (self.profile.city if self.profile else '') or self.instance.city
        contact = (self.profile.contact_text() if self.profile else '') or self.instance.contact
        return city, contact

    def clean(self):
        cleaned = super().clean()
        if self.profile is not None and not all(self._location()):
            raise forms.ValidationError('Lengkapi kota dan kontak di profil dulu, lalu coba lagi.')
        return cleaned

    def save(self, commit=True):
        listing = super().save(commit=False)
        if self.profile is not None:
            listing.city, listing.contact = self._location()
        if commit:
            listing.save()
            self.save_m2m()
        return listing

    def clean_image(self):
        """Reject uploads larger than 5 MB (Django already checks it is an image)."""
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size') and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Ukuran foto maksimal 5 MB.')
        return image
