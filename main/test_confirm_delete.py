"""Every delete button asks first, in the same themed pop-up (static/js/confirm-delete.js)."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from garden_journal.models import GardenJournal
from my_ecopatch.models import EcoPatch
from plant_library.models import Plant


class ConfirmDeleteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('petak', password='pw12345678')
        self.staff = get_user_model().objects.create_user('admin', password='pw12345678', is_staff=True)
        self.patch = EcoPatch.objects.create(owner=self.user, name='Balkon <b>Hijau</b>', space_type='balcony', city='Depok')
        self.plant = Plant.objects.create(
            name='Basil', category='herbs', sunlight='full', watering='moderate', difficulty='easy',
            indoor_outdoor='both', space_requirement='any')
        self.journal = GardenJournal.objects.create(
            user=self.user, plant_name='Basil', ecopatch_name='Balkon', date=datetime.date(2026, 10, 1),
            title='Hari pertama', notes='Tumbuh', plant_condition='healthy')

    def get(self, name, *args, user=None, **kwargs):
        self.client.force_login(user or self.user)
        return self.client.get(reverse(name, args=args), **kwargs).content.decode()

    def test_every_page_carries_the_shared_form_and_the_script(self):
        html = self.get('my_ecopatch:list')
        self.assertIn('id="site-delete-form"', html)
        self.assertIn('js/confirm-delete.js', html)
        self.assertIn('csrfmiddlewaretoken', html.split('id="site-delete-form"')[1].split('</form>')[0])

    def test_the_ecopatch_page_deletes_through_the_popup_and_keeps_its_fallback_link(self):
        html = self.get('my_ecopatch:detail', self.patch.pk)
        link = html[html.index('class="mep-link-danger"'):].split('</a>')[0]
        self.assertIn('data-confirm-delete', link)
        self.assertIn('data-confirm-title="Hapus EcoPatch?"', link)
        self.assertIn('data-confirm-name="Balkon &lt;b&gt;Hijau&lt;/b&gt;"', link)  # the name is escaped, never markup
        self.assertIn(reverse('my_ecopatch:delete', args=[self.patch.pk]), html)

    def test_the_plant_library_delete_buttons_open_the_popup(self):
        delete_url = reverse('plant_library:plant_delete', args=[self.plant.pk])
        for page in ('plant_library:plant_list', 'plant_library:plant_detail'):
            args = (self.plant.pk,) if page.endswith('detail') else ()
            html = self.get(page, *args, user=self.staff)
            self.assertIn('data-confirm-title="Hapus tanaman dari katalog?"', html)
            self.assertIn('data-confirm-name="Basil"', html)
            self.assertIn(delete_url, html)  # the link still leads to the confirmation page without JavaScript

    def test_a_visitor_who_is_not_staff_sees_no_plant_delete_button(self):
        self.assertNotIn('Hapus tanaman dari katalog?', self.get('plant_library:plant_list'))

    def test_the_journal_delete_forms_open_the_popup_and_fall_back_to_confirm(self):
        html = self.get('garden_journal:detail', self.journal.pk)
        form = html[html.index('data-confirm-delete'):][:600]
        self.assertIn('data-confirm-name="Hari pertama"', form)
        self.assertIn('window.siteConfirmDelete ? true : confirm(', html)

    def test_the_journal_history_page_uses_the_shared_popup_instead_of_its_own_toast(self):
        html = self.get('garden_journal:plant_history', 'Basil')
        self.assertIn('window.siteConfirmDelete({', html)
        self.assertNotIn('delete-confirm-toast', html)

    def test_no_delete_button_uses_the_browsers_plain_confirm_alone(self):
        for name, args in (('garden_journal:list', ()), ('garden_journal:detail', (self.journal.pk,))):
            html = self.get(name, *args)
            self.assertNotIn('onsubmit="return confirm(', html)

    def test_the_delete_endpoints_still_delete_and_only_for_the_owner(self):
        other = get_user_model().objects.create_user('lain', password='pw12345678')
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('my_ecopatch:delete', args=[self.patch.pk])).status_code, 404)
        self.assertTrue(EcoPatch.objects.filter(pk=self.patch.pk).exists())
        self.client.force_login(self.user)  # what the shared form does: a plain POST to the link's address
        self.client.post(reverse('my_ecopatch:delete', args=[self.patch.pk]))
        self.assertFalse(EcoPatch.objects.filter(pk=self.patch.pk).exists())
        self.client.post(reverse('garden_journal:delete', args=[self.journal.pk]))
        self.assertFalse(GardenJournal.objects.filter(pk=self.journal.pk).exists())
