import io
import tempfile
from datetime import date
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from my_ecopatch.models import EcoPatch
from .forms import GardenJournalForm
from .models import GardenJournal


def photo(name='plant.png', content_type='image/png'):
    data = io.BytesIO()
    Image.new('RGB', (8, 8), '#167a38').save(data, 'PNG')
    return SimpleUploadedFile(name, data.getvalue(), content_type=content_type)


class JournalRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('audit')
        cls.patch = EcoPatch.objects.create(owner=cls.user, name='Balkon', space_type='balcony', city='Depok')
        cls.journal = GardenJournal.objects.create(user=cls.user, ecopatch=cls.patch, plant_name='Bayam',
            title='Daun baru', date=date(2026, 10, 30), notes='Tumbuh sehat')

    def setUp(self):
        self.client.force_login(self.user)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        override = override_settings(MEDIA_ROOT=self.temp.name)
        override.enable()
        self.addCleanup(override.disable)

    def data(self, **changes):
        data = {'plant_name': 'Bayam', 'ecopatch': self.patch.pk, 'date': '2026-10-30',
                'title': 'Catatan baru', 'notes': 'Sehat', 'plant_condition': 'healthy', 'cover_pattern': 'flowers'}
        data.update(changes)
        return data

    def test_invalid_filter_dates_do_not_crash_list_or_ajax(self):
        for name in ('garden_journal:list', 'garden_journal:filter_ajax'):
            for field in ('date_from', 'date_to'):
                for value in ('invalid', '2026-99-99'):
                    with self.subTest(name=name, field=field, value=value):
                        self.assertEqual(self.client.get(reverse(name), {field: value}).status_code, 200)

    def test_invalid_history_date_does_not_crash(self):
        url = reverse('garden_journal:plant_history', args=['Bayam'])
        for value in ('invalid', '2026-02-31'):
            with self.subTest(value=value):
                self.assertEqual(self.client.get(url, {'date': value}).status_code, 200)

    def test_empty_plant_name_stays_on_form(self):
        response = self.client.post(reverse('garden_journal:create'), self.data(plant_name=''))
        self.assertEqual(response.status_code, 200)
        self.assertIn('plant_name', response.context['form'].errors)

    def test_plant_name_with_slash_can_be_created_and_opened(self):
        response = self.client.post(reverse('garden_journal:create'), self.data(plant_name='Basil / Mint'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(response.url).status_code, 200)

    def test_quick_upload_rejects_fake_image_bytes(self):
        response = self.client.post(reverse('garden_journal:upload_photo', args=[self.journal.pk]),
            {'image': SimpleUploadedFile('fake.png', b'not an image', content_type='image/png')})
        self.assertEqual(response.status_code, 400)
        self.journal.refresh_from_db()
        self.assertFalse(self.journal.image)

    def test_quick_upload_accepts_real_image(self):
        response = self.client.post(reverse('garden_journal:upload_photo', args=[self.journal.pk]), {'image': photo()})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_form_rejects_an_image_over_five_megabytes(self):
        image = photo()
        image.size = 5 * 1024 * 1024 + 1
        form = GardenJournalForm(self.data(), {'image': image}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('image', form.errors)

    def test_form_uses_jakarta_date_instead_of_host_date(self):
        local_date = date(2026, 10, 31)
        with patch('garden_journal.views.timezone.localdate', return_value=local_date):
            response = self.client.get(reverse('garden_journal:create'))
        self.assertEqual(response.context['form'].initial['date'], local_date)
