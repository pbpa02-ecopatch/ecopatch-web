from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from my_ecopatch.models import EcoPatch


class RecommendationInputRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('audit')
        cls.patch = EcoPatch.objects.create(owner=cls.user, name='Balkon', space_type='balcony', city='Depok')

    def test_invalid_patch_parameter_falls_back_to_an_owned_patch(self):
        self.client.force_login(self.user)
        for value in ('invalid', '²', '1.5', ''):
            with self.subTest(value=value):
                response = self.client.get(reverse('plant_library:plant_recommend'), {'patch': value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['selected_patch'], self.patch)
