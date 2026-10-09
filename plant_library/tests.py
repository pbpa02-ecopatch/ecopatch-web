from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from plant_library.forms import PlantForm
from plant_library.models import Plant

# URL configuration lengkap untuk testing agar seluruh navigasi di header.html berhasil di-reverse
test_urlpatterns = [
    path('', include('main.urls')),
    path('plants/', include('plant_library.urls')),
    path('my-ecopatch/', include('my_ecopatch.urls')),
    path('journal/', include('garden_journal.urls')),
    path('seed-exchange/', include('seed_exchange.urls')),
]


@override_settings(ROOT_URLCONF=__name__)
class PlantCRUDTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff_admin',
            password='password123',
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username='regular_user',
            password='password123',
            is_staff=False,
        )
        self.plant = Plant.objects.create(
            name='Kemangi',
            scientific_name='Ocimum basilicum',
            category=Plant.Category.HERBS,
            sunlight=Plant.Sunlight.FULL,
            watering=Plant.Watering.MODERATE,
            difficulty=Plant.Difficulty.EASY,
            indoor_outdoor=Plant.Placement.OUTDOOR,
            space_requirement=Plant.SpaceRequirement.BALCONY,
            description='Aroma wangi dan mudah dirawat.',
        )

    def test_plant_str_and_ordering(self):
        self.assertEqual(str(self.plant), 'Kemangi')

    def test_plant_form_valid(self):
        form_data = {
            'name': 'Pandan Wangi',
            'scientific_name': 'Pandanus amaryllifolius',
            'category': Plant.Category.AROMATIC_USEFUL,
            'sunlight': Plant.Sunlight.PARTIAL,
            'watering': Plant.Watering.HIGH,
            'difficulty': Plant.Difficulty.EASY,
            'indoor_outdoor': Plant.Placement.OUTDOOR,
            'space_requirement': Plant.SpaceRequirement.SMALL_YARD,
            'description': 'Daun aromatik serbaguna.',
            'image_url': '',
        }
        form = PlantForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_plant_list_view(self):
        response = self.client.get(reverse('plant_library:plant_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kemangi')

    def test_plant_list_search_and_filter(self):
        # Search match
        res_match = self.client.get(reverse('plant_library:plant_list') + '?q=keman')
        self.assertContains(res_match, 'Kemangi')

        # Search no match
        res_empty = self.client.get(reverse('plant_library:plant_list') + '?q=stroberi')
        self.assertNotContains(res_empty, 'Kemangi')
        self.assertContains(res_empty, 'Tidak ada tanaman ditemukan')

    def test_plant_detail_view(self):
        response = self.client.get(reverse('plant_library:plant_detail', args=[self.plant.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kemangi')
        self.assertContains(response, 'Ocimum basilicum')

    def test_create_access_control(self):
        create_url = reverse('plant_library:plant_create')

        # 1. Anonymous user -> redirect ke login
        res_anon = self.client.get(create_url)
        self.assertEqual(res_anon.status_code, 302)
        self.assertIn('login', res_anon.url)

        # 2. Regular user (non-staff) -> ditolak & redirect ke plant_list
        self.client.login(username='regular_user', password='password123')
        res_reg = self.client.get(create_url)
        self.assertEqual(res_reg.status_code, 302)
        self.assertRedirects(res_reg, reverse('plant_library:plant_list'))

        # 3. Staff user -> boleh akses (200 OK)
        self.client.login(username='staff_admin', password='password123')
        res_staff = self.client.get(create_url)
        self.assertEqual(res_staff.status_code, 200)

    def test_create_plant_post(self):
        self.client.login(username='staff_admin', password='password123')
        data = {
            'name': 'Lidah Mertua',
            'scientific_name': 'Sansevieria trifasciata',
            'category': Plant.Category.INDOOR_LOW_LIGHT,
            'sunlight': Plant.Sunlight.SHADE,
            'watering': Plant.Watering.LOW,
            'difficulty': Plant.Difficulty.EASY,
            'indoor_outdoor': Plant.Placement.INDOOR,
            'space_requirement': Plant.SpaceRequirement.INDOOR,
            'description': 'Tanaman pembersih udara.',
            'image_url': '',
        }
        response = self.client.post(reverse('plant_library:plant_create'), data=data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Plant.objects.filter(name='Lidah Mertua').exists())

    def test_update_plant_post(self):
        self.client.login(username='staff_admin', password='password123')
        edit_url = reverse('plant_library:plant_update', args=[self.plant.pk])
        data = {
            'name': 'Kemangi Ungu',
            'scientific_name': 'Ocimum basilicum var. purpurascens',
            'category': Plant.Category.HERBS,
            'sunlight': Plant.Sunlight.FULL,
            'watering': Plant.Watering.MODERATE,
            'difficulty': Plant.Difficulty.EASY,
            'indoor_outdoor': Plant.Placement.OUTDOOR,
            'space_requirement': Plant.SpaceRequirement.BALCONY,
            'description': 'Varian kemangi dengan daun ungu eksotis.',
            'image_url': '',
        }
        response = self.client.post(edit_url, data=data)
        self.assertEqual(response.status_code, 302)
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.name, 'Kemangi Ungu')

    def test_delete_plant_success(self):
        self.client.login(username='staff_admin', password='password123')
        del_url = reverse('plant_library:plant_delete', args=[self.plant.pk])

        # GET confirm delete
        res_get = self.client.get(del_url)
        self.assertEqual(res_get.status_code, 200)

        # POST delete
        res_post = self.client.post(del_url)
        self.assertEqual(res_post.status_code, 302)
        self.assertRedirects(res_post, reverse('plant_library:plant_list'))
        self.assertFalse(Plant.objects.filter(pk=self.plant.pk).exists())

    def test_delete_plant_protected_error(self):
        self.client.login(username='staff_admin', password='password123')
        del_url = reverse('plant_library:plant_delete', args=[self.plant.pk])

        with patch.object(Plant, 'delete', side_effect=ProtectedError('Cannot delete', [self.plant])):
            response = self.client.post(del_url, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'tidak dapat dihapus karena masih digunakan')
            # Pastikan plant masih ada
            self.assertTrue(Plant.objects.filter(pk=self.plant.pk).exists())


# Definisikan urlpatterns pada modul ini agar @override_settings(ROOT_URLCONF=__name__) bekerja
urlpatterns = test_urlpatterns
