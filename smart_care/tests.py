from datetime import date
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import CareTask
from .services import get_care_recommendation, get_weather_data


class CareTaskModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="salf", password="test12345")

    def test_default_is_completed_false(self):
        task = CareTask.objects.create(user=self.user, task_type="watering", due_date=date.today())
        self.assertFalse(task.is_completed)

    def test_str_representation(self):
        task = CareTask.objects.create(user=self.user, task_type="pruning", due_date=date(2026, 1, 1))
        self.assertEqual(str(task), "Pruning - 2026-01-01")


class WeatherServiceTests(TestCase):
    def _mock_response(self, temperature=33, rain_probability=80):
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {
            "current": {
                "temperature_2m": temperature,
                "relative_humidity_2m": 70,
                "precipitation": 1.2,
            },
            "hourly": {"precipitation_probability": [rain_probability]},
        }
        return response

    @patch("smart_care.services.requests.get")
    def test_get_weather_data_returns_parsed_dict(self, mock_get):
        mock_get.return_value = self._mock_response(temperature=30, rain_probability=40)
        weather = get_weather_data("Jakarta")
        self.assertEqual(weather["temperature"], 30)
        self.assertEqual(weather["rain_probability"], 40)
        mock_get.assert_called_once()

    def test_get_weather_data_unknown_city_returns_none(self):
        self.assertIsNone(get_weather_data("Atlantis"))

    def test_rain_recommendation_triggered(self):
        weather = {"temperature": 25, "rain_probability": 75}
        messages = get_care_recommendation(weather)
        self.assertIn("High chance of rain today. Check soil condition before watering.", messages)

    def test_heat_recommendation_triggered(self):
        weather = {"temperature": 35, "rain_probability": 10}
        messages = get_care_recommendation(weather)
        self.assertIn("Hot weather today. Check your plants' moisture.", messages)

    def test_no_recommendation_when_mild(self):
        weather = {"temperature": 25, "rain_probability": 10}
        self.assertEqual(get_care_recommendation(weather), [])


class CareTaskViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="salf", password="test12345")
        self.other_user = User.objects.create_user(username="other", password="test12345")
        self.task = CareTask.objects.create(user=self.user, task_type="watering", due_date=date.today())

        patcher = patch("smart_care.views.get_weather_data", return_value=None)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_guest_cannot_access_list(self):
        response = self.client.get(reverse("smart_care:list"))
        self.assertNotEqual(response.status_code, 200)

    def test_logged_in_user_sees_only_own_tasks(self):
        CareTask.objects.create(user=self.other_user, task_type="fertilizing", due_date=date.today())
        self.client.login(username="salf", password="test12345")
        response = self.client.get(reverse("smart_care:list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["tasks"]), [self.task])

    def test_create_task(self):
        self.client.login(username="salf", password="test12345")
        response = self.client.post(reverse("smart_care:create"), {
            "task_type": "harvesting",
            "due_date": "2026-10-01",
            "is_completed": False,
            "notes": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CareTask.objects.filter(task_type="harvesting", user=self.user).exists())

    def test_update_task(self):
        self.client.login(username="salf", password="test12345")
        response = self.client.post(reverse("smart_care:update", args=[self.task.id]), {
            "task_type": "watering",
            "due_date": self.task.due_date,
            "is_completed": False,
            "notes": "watered lightly",
        })
        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.notes, "watered lightly")

    def test_delete_task(self):
        self.client.login(username="salf", password="test12345")
        response = self.client.post(reverse("smart_care:delete", args=[self.task.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CareTask.objects.filter(id=self.task.id).exists())

    def test_user_cannot_access_other_users_task(self):
        self.client.login(username="other", password="test12345")
        response = self.client.get(reverse("smart_care:detail", args=[self.task.id]))
        self.assertEqual(response.status_code, 404)

    def test_mark_as_completed_via_ajax(self):
        self.client.login(username="salf", password="test12345")
        response = self.client.post(reverse("smart_care:complete", args=[self.task.id]))
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_completed)

    def test_filter_by_due_date(self):
        other_date = date(2026, 12, 25)
        CareTask.objects.create(user=self.user, task_type="pruning", due_date=other_date)
        self.client.login(username="salf", password="test12345")
        response = self.client.get(reverse("smart_care:list"), {"due_date": str(other_date)})
        tasks = list(response.context["tasks"])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].due_date, other_date)
