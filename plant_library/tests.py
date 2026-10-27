from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from my_ecopatch.models import EcoPatch
from plant_library.forms import PlantForm
from plant_library.models import Plant
from plant_library.views import parse_query_keywords

# URL configuration lengkap untuk testing agar seluruh navigasi di header.html berhasil di-reverse
test_urlpatterns = [
    path('', include('main.urls')),
    path('plants/', include('plant_library.urls')),
    path('smart-care/', include('smart_care.urls')),
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
        # moderate watering and outdoor: the Smart Care interval is shown
        self.assertContains(response, 'Smart Care menyarankan menyiram sekitar tiap 2 hari')

    def test_plant_detail_shows_the_matching_ecopatch_name(self):
        patch = EcoPatch.objects.create(
            owner=self.regular_user,
            name='Balkon Kosan',
            space_type=EcoPatch.SpaceType.BALCONY,
            sunlight=EcoPatch.Sunlight.FULL,
            city='Depok',
        )
        self.client.login(username='regular_user', password='password123')
        response = self.client.get(reverse('plant_library:plant_detail', args=[self.plant.pk]))
        self.assertContains(response, f'Cocok untuk {patch.name}')

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

    def test_recommend_requires_login(self):
        url = reverse('plant_library:plant_recommend')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        self.assertIn('login', res.url)

    def test_recommend_no_ecopatch(self):
        self.client.login(username='regular_user', password='password123')
        url = reverse('plant_library:plant_recommend')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'belum memiliki EcoPatch')

    def test_recommend_with_ecopatch(self):
        patch = EcoPatch.objects.create(
            owner=self.regular_user,
            name='Balkon Kosan',
            space_type=EcoPatch.SpaceType.BALCONY,
            sunlight=EcoPatch.Sunlight.FULL,
            city='Depok',
        )
        indoor_plant = Plant.objects.create(
            name='Sansevieria Test',
            category=Plant.Category.INDOOR_LOW_LIGHT,
            sunlight=Plant.Sunlight.SHADE,
            watering=Plant.Watering.LOW,
            difficulty=Plant.Difficulty.EASY,
            indoor_outdoor=Plant.Placement.INDOOR,
            space_requirement=Plant.SpaceRequirement.INDOOR,
        )

        self.client.login(username='regular_user', password='password123')
        url = reverse('plant_library:plant_recommend')
        res = self.client.get(url, {'patch': patch.pk})

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Kemangi')
        self.assertNotContains(res, 'Sansevieria Test')


# Definisikan urlpatterns pada modul ini agar @override_settings(ROOT_URLCONF=__name__) bekerja
urlpatterns = test_urlpatterns


# =============================================================================
# Tes fungsi parse_query_keywords (logika pemetaan kata kunci)
# =============================================================================
class ParseQueryKeywordsTests(TestCase):
    """Unit test untuk fungsi parse_query_keywords di views.py."""

    def test_keyword_natural_sentence_easy_shade(self):
        """'tanaman yang mudah dirawat dan teduh' → difficulty=easy, sunlight=shade, tidak ada sisa teks."""
        filters, remaining = parse_query_keywords("tanaman yang mudah dirawat dan teduh")
        self.assertEqual(filters.get("difficulty"), "easy")
        self.assertEqual(filters.get("sunlight"), "shade")
        self.assertEqual(remaining, "")

    def test_keyword_plain_name(self):
        """'bayam' tidak dipetakan ke filter, sisa teks = 'bayam'."""
        filters, remaining = parse_query_keywords("bayam")
        self.assertEqual(filters, {})
        self.assertEqual(remaining, "bayam")

    def test_keyword_mixed_filter_and_name(self):
        """'mudah bayam' → difficulty=easy, sisa teks = 'bayam'."""
        filters, remaining = parse_query_keywords("mudah bayam")
        self.assertEqual(filters.get("difficulty"), "easy")
        self.assertEqual(remaining, "bayam")

    def test_keyword_single_shade(self):
        """'teduh' → sunlight=shade."""
        filters, remaining = parse_query_keywords("teduh")
        self.assertEqual(filters.get("sunlight"), "shade")
        self.assertEqual(remaining, "")

    def test_keyword_indoor(self):
        """'indoor' → indoor_outdoor=indoor."""
        filters, remaining = parse_query_keywords("indoor")
        self.assertEqual(filters.get("indoor_outdoor"), "indoor")

    def test_keyword_cahaya_penuh(self):
        """'cahaya penuh' → sunlight=full."""
        filters, remaining = parse_query_keywords("cahaya penuh")
        self.assertEqual(filters.get("sunlight"), "full")
        self.assertEqual(remaining, "")

    def test_keyword_no_double_group(self):
        """Satu kelompok tidak boleh diklaim dua kali: frasa terpanjang menang."""
        # "mudah dirawat" harus diprioritaskan atas "mudah"
        filters, remaining = parse_query_keywords("mudah dirawat")
        self.assertEqual(filters.get("difficulty"), "easy")
        self.assertEqual(remaining, "")

    def test_keyword_trailing_punctuation_is_ignored(self):
        """'mudah/' tetap terbaca sebagai filter mudah, bukan nama tanaman."""
        filters, remaining = parse_query_keywords("mudah/")
        self.assertEqual(filters.get("difficulty"), "easy")
        self.assertEqual(remaining, "")

    def test_a_question_leaves_only_the_filters(self):
        """Kata tanya bukan nama tanaman: kalimat saran dari landing page hanya menghasilkan filter."""
        cases = {
            "Tanaman apa yang mudah dirawat di dalam ruangan?": {"difficulty": "easy", "indoor_outdoor": "indoor"},
            "Tanaman apa yang cocok di luar ruangan dengan cahaya penuh?": {"indoor_outdoor": "outdoor", "sunlight": "full"},
            "Tanaman apa yang teduh dan mudah dirawat?": {"sunlight": "shade", "difficulty": "easy"},
            "Apa tanaman outdoor dengan perawatan sedang?": {"indoor_outdoor": "outdoor", "difficulty": "medium"},
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                filters, remaining = parse_query_keywords(question)
                self.assertEqual(filters, expected)
                self.assertEqual(remaining, "")

    def test_a_real_plant_name_in_a_question_is_still_searched(self):
        filters, remaining = parse_query_keywords("Apa bayam cocok di luar ruangan?")
        self.assertEqual(filters, {"indoor_outdoor": "outdoor"})
        self.assertEqual(remaining, "bayam")


@override_settings(ROOT_URLCONF=__name__)
class KeywordSearchIntegrationTests(TestCase):
    """Tes integrasi: keyword search menghasilkan queryset yang tepat lewat view."""

    def setUp(self):
        self.easy_shade = Plant.objects.create(
            name="Pakis Haji",
            category=Plant.Category.INDOOR_LOW_LIGHT,
            sunlight=Plant.Sunlight.SHADE,
            watering=Plant.Watering.LOW,
            difficulty=Plant.Difficulty.EASY,
            indoor_outdoor=Plant.Placement.INDOOR,
            space_requirement=Plant.SpaceRequirement.INDOOR,
        )
        self.hard_full = Plant.objects.create(
            name="Bayam Merah",
            category=Plant.Category.VEGETABLES,
            sunlight=Plant.Sunlight.FULL,
            watering=Plant.Watering.HIGH,
            difficulty=Plant.Difficulty.HARD,
            indoor_outdoor=Plant.Placement.OUTDOOR,
            space_requirement=Plant.SpaceRequirement.BALCONY,
        )

    def test_view_natural_sentence_easy_shade(self):
        """'tanaman yang mudah dirawat dan teduh' harus muncul Pakis Haji, bukan Bayam Merah."""
        url = reverse("plant_library:plant_list") + "?q=tanaman+yang+mudah+dirawat+dan+teduh"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Pakis Haji")
        self.assertNotContains(res, "Bayam Merah")

    def test_view_plain_name_search(self):
        """'bayam' harus menemukan Bayam Merah lewat name__icontains."""
        url = reverse("plant_library:plant_list") + "?q=bayam"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Bayam Merah")
        self.assertNotContains(res, "Pakis Haji")

    def test_view_keyword_with_trailing_slash_still_filters(self):
        """'mudah/' tidak boleh dianggap nama tanaman; filter mudah tetap jalan."""
        url = reverse("plant_library:plant_list") + "?q=mudah%2F"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Pakis Haji")
        self.assertNotContains(res, "Bayam Merah")

    def test_view_mixed_easy_bayam(self):
        """'mudah bayam' → filter difficulty=easy DAN nama mengandung 'bayam'.
        Bayam Merah adalah hard, jadi tidak muncul; Pakis Haji ada nama 'bayam'? Tidak.
        Hasil: 0 tanaman (benar, keduanya tidak lolos kedua filter)."""
        url = reverse("plant_library:plant_list") + "?q=mudah+bayam"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        # Pakis Haji lolos easy tapi namanya tidak mengandung 'bayam',
        # Bayam Merah mengandung 'bayam' tapi difficulty=hard → 0 hasil
        self.assertContains(res, "Tidak ada tanaman ditemukan")


class WateringIntervalTests(TestCase):
    """Plant.watering_interval_days: the days between two waterings that Smart Care schedules by."""

    def plant(self, watering, **kwargs):
        values = dict(
            name='Uji', category=Plant.Category.VEGETABLES, sunlight=Plant.Sunlight.FULL, watering=watering,
            difficulty=Plant.Difficulty.EASY, indoor_outdoor=Plant.Placement.OUTDOOR,
            space_requirement=Plant.SpaceRequirement.BALCONY,
        )
        values.update(kwargs)
        return Plant(**values)

    def test_base_days_follow_how_often_the_plant_wants_water(self):
        self.assertEqual(self.plant(Plant.Watering.HIGH).watering_interval_days, 1)
        self.assertEqual(self.plant(Plant.Watering.MODERATE).watering_interval_days, 2)
        self.assertEqual(self.plant(Plant.Watering.LOW).watering_interval_days, 4)

    def test_an_indoor_plant_dries_slower(self):
        indoor = self.plant(Plant.Watering.MODERATE, indoor_outdoor=Plant.Placement.INDOOR)
        self.assertEqual(indoor.watering_interval_days, 3)

    def test_an_indoor_low_light_plant_dries_slower_even_when_placement_is_both(self):
        plant = self.plant(Plant.Watering.MODERATE, category=Plant.Category.INDOOR_LOW_LIGHT,
                           indoor_outdoor=Plant.Placement.BOTH)
        self.assertEqual(plant.watering_interval_days, 3)

    def test_indoor_and_low_light_count_once_together(self):
        plant = self.plant(Plant.Watering.MODERATE, category=Plant.Category.INDOOR_LOW_LIGHT,
                           indoor_outdoor=Plant.Placement.INDOOR)
        self.assertEqual(plant.watering_interval_days, 3)

    def test_shade_adds_a_day(self):
        shade = self.plant(Plant.Watering.LOW, sunlight=Plant.Sunlight.SHADE)
        self.assertEqual(shade.watering_interval_days, 5)

    def test_never_longer_than_six_days(self):
        plant = self.plant(Plant.Watering.LOW, sunlight=Plant.Sunlight.SHADE,
                           indoor_outdoor=Plant.Placement.INDOOR)
        self.assertEqual(plant.watering_interval_days, 6)

    def test_the_seed_plants_spread_from_daily_to_every_six_days(self):
        from django.core.management import call_command
        call_command('loaddata', 'initial_plants', verbosity=0)
        days = {plant.name: plant.watering_interval_days for plant in Plant.objects.all()}
        self.assertEqual(days['Bayam Hijau'], 1)
        self.assertEqual(days['Cabai Rawit Merah'], 2)
        self.assertEqual(days['Rosemary'], 4)
        self.assertEqual(days['Lidah Mertua (Sansevieria)'], 6)
        self.assertTrue(all(1 <= value <= 6 for value in days.values()))
