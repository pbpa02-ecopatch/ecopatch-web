from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import EcoPatch


class QuickAddInputRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('audit')
        cls.patch = EcoPatch.objects.create(owner=cls.user, name='Balkon', space_type='balcony', city='Depok')

    def test_non_decimal_digit_is_rejected_without_server_error(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('my_ecopatch:plant_quick_add', args=[self.patch.pk]), {'plant': '²'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.patch.plants.exists())
