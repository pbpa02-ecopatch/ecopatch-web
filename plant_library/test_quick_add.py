"""The + on a plant card: put the plant into one of my EcoPatches without leaving the Plant Library."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from my_ecopatch.models import EcoPatch, PatchPlant
from plant_library.models import Plant
from plant_library.views import fit_hint

IMG = '<img src=x onerror=alert(1)>'


def make_plant(name='Basil', **kwargs):
    values = dict(category='herbs', sunlight='full', watering='moderate', difficulty='easy',
                  indoor_outdoor='both', space_requirement='any')
    values.update(kwargs)
    return Plant.objects.create(name=name, **values)


class FitHintTests(TestCase):
    def patch(self, **kwargs):
        values = dict(owner=get_user_model().objects.create_user('p' + str(EcoPatch.objects.count())), name='Kebun',
                      space_type='balcony', city='Depok')
        values.update(kwargs)
        return EcoPatch.objects.create(**values)

    def test_a_plant_that_fits_says_so(self):
        self.assertEqual(fit_hint(make_plant(), self.patch(sunlight='full')), ('ok', 'Cocok'))

    def test_a_bright_plant_indoors_gets_a_placement_tip(self):
        tone, text = fit_hint(make_plant(), self.patch(space_type='indoor'))
        self.assertEqual((tone, text), ('tip', 'Taruh dekat jendela yang terang'))

    def test_a_shade_plant_outdoors_gets_a_placement_tip(self):
        tone, text = fit_hint(make_plant('Mint', sunlight='shade'), self.patch())
        self.assertEqual((tone, text), ('tip', 'Taruh di sudut yang teduh'))

    def test_the_wrong_space_is_a_warning(self):
        tone, text = fit_hint(make_plant(space_requirement='rooftop'), self.patch(space_type='indoor'))
        self.assertEqual(tone, 'warn')
        self.assertIn('Butuh ruang', text)

    def test_the_wrong_light_is_a_warning(self):
        tone, text = fit_hint(make_plant(sunlight='full'), self.patch(sunlight='shade'))
        self.assertEqual((tone, text), ('warn', 'Butuh cahaya penuh'))


class CardAddButtonTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('petak', password='pw12345678')
        self.plant = make_plant()
        self.patch = EcoPatch.objects.create(owner=self.user, name=IMG, space_type='terrace', city='Malang')

    def test_a_guest_sees_no_add_button(self):
        self.assertNotContains(self.client.get(reverse('plant_library:plant_list')), 'data-plant-add')

    def test_a_member_gets_a_button_and_a_row_per_ecopatch_with_the_name_escaped(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('plant_library:plant_list'))
        self.assertContains(response, 'data-plant-add')
        self.assertContains(response, reverse('my_ecopatch:plant_quick_add', args=[self.patch.pk]))
        self.assertContains(response, 'Teras · Malang')
        self.assertNotContains(response, IMG)
        self.assertContains(response, '&lt;img src=x onerror=alert(1)&gt;')

    def test_a_plant_already_in_an_ecopatch_is_marked(self):
        PatchPlant.objects.create(patch=self.patch, plant=self.plant, quantity=1, status='planned')
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('plant_library:plant_list')), 'Sudah ada di sini')

    def test_the_recommendation_page_has_the_button_too(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('plant_library:plant_recommend'))
        self.assertContains(response, 'data-plant-add')

    def test_without_an_ecopatch_the_list_points_to_making_one(self):
        self.patch.delete()
        self.client.force_login(self.user)
        response = self.client.get(reverse('plant_library:plant_list'))
        self.assertContains(response, 'Kamu belum punya EcoPatch.')
        self.assertContains(response, reverse('my_ecopatch:create'))


class PlantPopupTests(TestCase):
    """A card opens the plant sheet in a pop-up: the same sheet, asked for without the page around it."""

    def setUp(self):
        self.plant = make_plant(name=IMG, description='Segar <b>sekali</b>')
        self.url = reverse('plant_library:plant_detail', args=[self.plant.pk])

    def test_asked_as_a_popup_it_returns_only_the_sheet(self):
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('<html', html)
        self.assertIn('id="plant-modal-title"', html)
        self.assertIn('data-plant-close', html)
        self.assertNotIn('Kembali ke Plant Library', html)
        self.assertIn('Buka halaman lengkap', html)

    def test_the_same_address_still_works_as_a_page(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('<html', html)
        self.assertIn('Kembali ke Plant Library', html)
        self.assertNotIn('plant-modal-title', html)
        self.assertNotIn('data-plant-close', html)

    def test_the_two_answers_are_not_mixed_up_by_a_cache(self):
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIn('X-Requested-With', response['Vary'])

    def test_typed_text_is_escaped_in_the_popup(self):
        html = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest').content.decode()
        self.assertNotIn(IMG, html)
        self.assertNotIn('<b>sekali</b>', html)
        self.assertIn('&lt;b&gt;sekali&lt;/b&gt;', html)

    def test_cards_mark_what_opens_the_popup_and_load_its_script(self):
        response = self.client.get(reverse('plant_library:plant_list'))
        self.assertContains(response, 'data-plant-open')
        self.assertContains(response, 'plant_library/js/detail_modal.js')

    def test_staff_keep_their_edit_buttons_in_the_popup(self):
        staff = get_user_model().objects.create_user('admin', password='pw12345678', is_staff=True)
        self.client.force_login(staff)
        html = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest').content.decode()
        self.assertIn(reverse('plant_library:plant_update', args=[self.plant.pk]), html)
