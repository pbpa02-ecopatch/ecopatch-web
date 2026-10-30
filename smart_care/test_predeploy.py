from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone


class CalendarBoundaryRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('audit')

    def test_calendar_extremes_fall_back_without_overflow(self):
        self.client.force_login(self.user)
        for value in ('0001-01-01', '0001-01-07', '9999-12-25', '9999-12-31'):
            with self.subTest(value=value):
                response = self.client.get(reverse('smart_care:list'), {'date': value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['selected_date'], timezone.localdate())
