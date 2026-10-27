from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from main.models import Profile
from plant_library.models import Plant
from smart_care.models import CareTask
from .models import EcoPatch, PatchPlant


class GardenUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username='gardener')
        cls.other = get_user_model().objects.create_user(username='other')
        cls.patch = EcoPatch.objects.create(owner=cls.owner, name='Balkon Hijau', space_type='balcony', city='Depok')
        cls.private = EcoPatch.objects.create(owner=cls.other, name='Private Garden', space_type='indoor', city='Bogor')
        cls.catalog = Plant.objects.create(name='Basil', category='herbs', sunlight='partial', watering='moderate', difficulty='easy', indoor_outdoor='both', space_requirement='any')
        cls.plant = PatchPlant.objects.create(patch=cls.patch, plant=cls.catalog, quantity=4, status='growing')

    def setUp(self):
        self.client.force_login(self.owner)

    def url(self, name, pk=None):
        return reverse('my_ecopatch:' + name, args=[pk] if pk else [])

    def test_list_is_private_and_totals_use_quantity(self):
        response = self.client.get(self.url('list'))
        self.assertContains(response, 'Balkon Hijau')
        self.assertNotContains(response, 'Private Garden')
        self.assertEqual(response.context['plant_count'], 4)
        self.assertEqual(response.context['growing_count'], 4)
        self.assertEqual(response.context['patch_count'], 1)
        self.assertContains(response, 'my_ecopatch/garden.css')

    def test_filters_and_reset_do_not_change_global_totals(self):
        for params, count in [({'q': 'depok'}, 1), ({'q': 'absent'}, 0), ({'space': 'indoor'}, 0), ({'space': 'invalid'}, 1)]:
            with self.subTest(params=params):
                response = self.client.get(self.url('list'), params)
                self.assertEqual(len(response.context['patches']), count)
                self.assertEqual(response.context['plant_count'], 4)

    def test_create_update_delete_patch(self):
        data = {'name': 'Teras Baru', 'space_type': 'terrace', 'city': 'Jakarta', 'size_m2': 4, 'sunlight': 'full', 'goal': 'Sayur segar'}
        response = self.client.post(self.url('create'), data)
        patch = EcoPatch.objects.get(name='Teras Baru')
        self.assertRedirects(response, self.url('detail', patch.pk))
        self.assertEqual(patch.owner, self.owner)
        data['name'] = 'Teras Baru Lagi'
        self.assertRedirects(self.client.post(self.url('update', patch.pk), data), self.url('detail', patch.pk))
        patch.refresh_from_db()
        self.assertEqual(patch.name, data['name'])
        self.assertContains(self.client.get(self.url('delete', patch.pk)), 'Hapus EcoPatch?')
        self.assertTrue(EcoPatch.objects.filter(pk=patch.pk).exists())
        self.assertRedirects(self.client.post(self.url('delete', patch.pk)), self.url('list'))
        self.assertFalse(EcoPatch.objects.filter(pk=patch.pk).exists())

    def test_the_form_does_not_ask_for_a_city_and_shows_the_profile_one(self):
        Profile.objects.update_or_create(user=self.owner, defaults={'city': 'Bandung'})
        response = self.client.get(self.url('create'))
        self.assertNotIn('city', response.context['form'].fields)
        self.assertNotContains(response, 'name="city"')
        self.assertContains(response, 'Kota ikut profilmu: <strong>Bandung</strong>')

    def test_a_new_patch_takes_its_city_from_the_profile_not_from_the_post(self):
        Profile.objects.update_or_create(user=self.owner, defaults={'city': 'Bandung'})
        self.client.post(self.url('create'), {'name': 'Kebun Profil', 'space_type': 'terrace', 'city': 'Medan'})
        self.assertEqual(EcoPatch.objects.get(name='Kebun Profil').city, 'Bandung')

    def test_editing_a_patch_follows_the_current_profile_city(self):
        Profile.objects.update_or_create(user=self.owner, defaults={'city': 'Malang'})
        self.client.post(self.url('update', self.patch.pk), {'name': 'Balkon Hijau', 'space_type': 'balcony'})
        self.patch.refresh_from_db()
        self.assertEqual(self.patch.city, 'Malang')

    def test_without_a_profile_city_nothing_is_invented_and_the_page_points_to_the_profile(self):
        response = self.client.get(self.url('create'))
        self.assertContains(response, 'Kotamu belum diisi di profil')
        self.client.post(self.url('create'), {'name': 'Tanpa Kota', 'space_type': 'terrace'})
        self.assertEqual(EcoPatch.objects.get(name='Tanpa Kota').city, '')
        self.client.post(self.url('update', self.patch.pk), {'name': 'Balkon Hijau', 'space_type': 'balcony'})
        self.patch.refresh_from_db()
        self.assertEqual(self.patch.city, 'Depok')
        self.assertNotContains(self.client.get(self.url('list')), 'Terrace · ')

    def test_empty_and_invalid_form(self):
        self.client.force_login(self.other)
        EcoPatch.objects.filter(owner=self.other).delete()
        self.assertContains(self.client.get(self.url('list')), 'Ruang kecil, awal yang berarti.')
        response = self.client.post(self.url('create'), {'name': 'Keep this name'})
        self.assertContains(response, 'Keep this name')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertFalse(EcoPatch.objects.filter(owner=self.other).exists())

    def test_add_plant_normal_and_htmx(self):
        data = {'plant': self.catalog.pk, 'quantity': 2, 'status': 'planted', 'planted_at': '2026-10-27'}
        for ajax in [False, True]:
            with self.subTest(ajax=ajax):
                response = self.client.post(self.url('plant_add', self.patch.pk), data, **({'HTTP_HX_REQUEST': 'true'} if ajax else {}))
                if ajax:
                    self.assertContains(response, 'berhasil ditambahkan')
                    self.assertNotContains(response, '<html')
                else:
                    self.assertRedirects(response, self.url('detail', self.patch.pk))
        saved = self.patch.plants.last()
        self.assertEqual(saved.quantity, 2)
        self.assertEqual(str(saved.planted_at), '2026-10-27')
        self.assertEqual(saved.plant, self.catalog)

    def test_invalid_add_preserves_input_and_database(self):
        response = self.client.post(self.url('plant_add', self.patch.pk), {'plant': self.catalog.pk, 'quantity': 0, 'status': 'growing'}, HTTP_HX_REQUEST='true')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertEqual(response.context['plant_form']['plant'].value(), str(self.catalog.pk))
        self.assertEqual(self.patch.plants.count(), 1)

    def test_all_statuses_and_invalid_status(self):
        for value in PatchPlant.Status.values:
            response = self.client.post(self.url('plant_status', self.plant.pk), {'status': value}, HTTP_HX_REQUEST='true')
            self.assertContains(response, 'Status tanaman berhasil disimpan.')
            self.plant.refresh_from_db()
            self.assertEqual(self.plant.status, value)
        self.assertEqual(self.client.post(self.url('plant_status', self.plant.pk), {'status': 'bad'}).status_code, 400)
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.status, 'removed')

    def test_delete_confirmation_and_care_history(self):
        task = CareTask.objects.create(user=self.owner, patch_plant=self.plant, plant_name='Basil', task_type='watering')
        response = self.client.get(self.url('plant_delete', self.plant.pk))
        self.assertContains(response, 'Hapus tanaman?')
        self.assertTrue(PatchPlant.objects.filter(pk=self.plant.pk).exists())
        self.assertContains(self.client.post(self.url('plant_delete', self.plant.pk), HTTP_HX_REQUEST='true'), 'Tanaman berhasil dihapus.')
        task.refresh_from_db()
        self.assertIsNone(task.patch_plant_id)
        self.assertFalse(PatchPlant.objects.filter(pk=self.plant.pk).exists())

    def test_ownership_on_every_route(self):
        self.client.force_login(self.other)
        for name in ['detail', 'update', 'delete', 'plant_add']:
            self.assertEqual(self.client.post(self.url(name, self.patch.pk)).status_code, 404)
        for name in ['plant_status', 'plant_delete']:
            self.assertEqual(self.client.post(self.url(name, self.plant.pk), {'status': 'growing'}).status_code, 404)

    def test_authentication_csrf_and_post_only(self):
        self.assertEqual(self.client.get(self.url('plant_add', self.patch.pk)).status_code, 405)
        self.assertEqual(self.client.get(self.url('plant_status', self.plant.pk)).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(strict.post(self.url('plant_delete', self.plant.pk)).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url('list')).status_code, 302)

    def test_legacy_plant_and_library_preselection(self):
        PatchPlant.objects.create(patch=self.patch, plant_name='Tanaman lama', quantity=3)
        response = self.client.get(self.url('detail', self.patch.pk), {'plant': self.catalog.pk})
        self.assertContains(response, 'Tanaman lama')
        self.assertEqual(response.context['plant_form']['plant'].value(), str(self.catalog.pk))
        self.assertEqual(response.context['patch'].plant_quantity, 7)

    def test_long_and_html_names_are_escaped(self):
        self.patch.name = '<script>alert(1)</script>'
        self.patch.save()
        response = self.client.get(self.url('list'))
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
