from datetime import timedelta
from unittest.mock import Mock, patch

import requests
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import CareTask
from .services import get_recommendation, get_weather

WEATHER_OK = {
    "city": "Depok",
    "available": True,
    "temperature": 29.4,
    "humidity": 80,
    "rain_probability": 75,
    "condition": "Rain",
}
WEATHER_DOWN = {
    "city": "Depok",
    "available": False,
    "temperature": None,
    "humidity": None,
    "rain_probability": None,
    "condition": None,
}


def make_task(user, **kwargs):
    fields = {"task_type": "watering", "due_date": timezone.localdate(), "city": "Depok"}
    fields.update(kwargs)
    return CareTask.objects.create(user=user, **fields)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CareTaskModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass12345")

    def test_is_completed_defaults_to_false(self):
        task = make_task(self.user)
        self.assertFalse(task.is_completed)

    def test_str_uses_display_label_and_due_date(self):
        task = make_task(self.user, task_type="fertilizing", due_date=timezone.datetime(2026, 10, 1).date())
        self.assertEqual(str(task), "Fertilizing - 2026-10-01")


class WeatherServiceTests(TestCase):
    @patch("smart_care.services.requests.get")
    def test_parses_open_meteo_response(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            raise_for_status=Mock(),
            json=Mock(return_value={"current": {
                "temperature_2m": 33.1,
                "relative_humidity_2m": 60,
                "precipitation_probability": 10,
                "weather_code": 0,
            }}),
        )
        weather = get_weather("Bandung")

        self.assertTrue(weather["available"])
        self.assertEqual(weather["temperature"], 33.1)
        self.assertEqual(weather["humidity"], 60)
        self.assertEqual(weather["rain_probability"], 10)
        self.assertEqual(weather["condition"], "Clear")
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual((params["latitude"], params["longitude"]), (-6.91, 107.61))

    @patch("smart_care.services.requests.get", side_effect=requests.Timeout)
    def test_api_failure_returns_fallback(self, mock_get):
        with self.assertLogs("smart_care.services", level="WARNING"):
            weather = get_weather("Depok")
        self.assertFalse(weather["available"])
        self.assertIsNone(weather["temperature"])
        self.assertIsNone(weather["humidity"])
        self.assertIsNone(weather["rain_probability"])
        self.assertIsNone(weather["condition"])

    @patch("smart_care.services.requests.get")
    def test_unknown_city_skips_api(self, mock_get):
        weather = get_weather("Atlantis")
        self.assertFalse(weather["available"])
        mock_get.assert_not_called()

    def test_recommendation_rules(self):
        self.assertIn("rain", get_recommendation({"rain_probability": 70, "temperature": 35}))
        self.assertIn("Hot", get_recommendation({"rain_probability": 10, "temperature": 32}))
        self.assertIsNone(get_recommendation({"rain_probability": 10, "temperature": 28}))
        self.assertIsNone(get_recommendation(WEATHER_DOWN))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
@patch("smart_care.views.get_weather", return_value=WEATHER_OK)
class CareTaskViewTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pass12345")
        self.bob = User.objects.create_user("bob", password="pass12345")
        self.task = make_task(self.alice)
        self.bob_task = make_task(self.bob, task_type="pruning")
        self.client.login(username="alice", password="pass12345")

    def test_guest_is_redirected_to_login_everywhere(self, _weather):
        self.client.logout()
        login_url = reverse("main:login")
        pk = self.task.pk
        requests_to_make = [
            ("get", reverse("smart_care:list")),
            ("get", reverse("smart_care:create")),
            ("post", reverse("smart_care:create")),
            ("get", reverse("smart_care:update", args=[pk])),
            ("post", reverse("smart_care:delete", args=[pk])),
            ("post", reverse("smart_care:complete", args=[pk])),
        ]
        for method, url in requests_to_make:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(login_url))
        self.assertTrue(CareTask.objects.filter(pk=pk, is_completed=False).exists())

    def test_list_shows_only_own_tasks_and_weather(self, _weather):
        response = self.client.get(reverse("smart_care:list"), {"city": "Depok"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["tasks"]), [self.task])
        self.assertNotContains(response, "Pruning")
        self.assertContains(response, "29°C")
        self.assertContains(response, "High chance of rain today")

    def test_list_filters_by_date(self, _weather):
        tomorrow = timezone.localdate() + timedelta(days=1)
        later = make_task(self.alice, task_type="harvesting", due_date=tomorrow)
        response = self.client.get(reverse("smart_care:list"), {"date": tomorrow.isoformat()})
        self.assertEqual(list(response.context["tasks"]), [later])

    def test_list_default_hides_past_tasks_and_counts_overdue(self, _weather):
        past = make_task(self.alice, due_date=timezone.localdate() - timedelta(days=3))
        response = self.client.get(reverse("smart_care:list"))
        self.assertNotIn(past, response.context["tasks"])
        self.assertEqual(response.context["stats"]["overdue"], 1)

    def test_list_shows_fallback_when_weather_unavailable(self, weather):
        weather.return_value = WEATHER_DOWN
        response = self.client.get(reverse("smart_care:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Info cuaca sedang tidak tersedia")
        self.assertIsNone(response.context["recommendation"])

    def test_create_and_update_forms_render(self, _weather):
        response = self.client.get(reverse("smart_care:create"), {"city": "Bogor"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["city"], "Bogor")
        response = self.client.get(reverse("smart_care:update", args=[self.task.pk]))
        self.assertContains(response, "Simpan Perubahan")

    def test_create_assigns_logged_in_user(self, _weather):
        response = self.client.post(reverse("smart_care:create"), {
            "task_type": "inspection",
            "city": "Bogor",
            "due_date": timezone.localdate().isoformat(),
            "notes": "Cek hama daun",
        })
        self.assertEqual(response.status_code, 302)
        task = CareTask.objects.get(task_type="inspection")
        self.assertEqual(task.user, self.alice)
        self.assertEqual(task.city, "Bogor")

    def test_update_own_task(self, _weather):
        response = self.client.post(reverse("smart_care:update", args=[self.task.pk]), {
            "task_type": "repotting",
            "city": "Depok",
            "due_date": timezone.localdate().isoformat(),
            "notes": "",
        })
        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.task_type, "repotting")

    def test_delete_own_task(self, _weather):
        response = self.client.post(reverse("smart_care:delete", args=[self.task.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CareTask.objects.filter(pk=self.task.pk).exists())

    def test_delete_requires_post(self, _weather):
        response = self.client.get(reverse("smart_care:delete", args=[self.task.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(CareTask.objects.filter(pk=self.task.pk).exists())

    def test_cannot_touch_other_users_task(self, _weather):
        pk = self.bob_task.pk
        self.assertEqual(self.client.get(reverse("smart_care:update", args=[pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("smart_care:update", args=[pk]), {
            "task_type": "watering", "city": "Depok", "due_date": timezone.localdate().isoformat(),
        }).status_code, 404)
        self.assertEqual(self.client.post(reverse("smart_care:delete", args=[pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("smart_care:complete", args=[pk])).status_code, 404)
        self.bob_task.refresh_from_db()
        self.assertEqual(self.bob_task.task_type, "pruning")
        self.assertFalse(self.bob_task.is_completed)

    def test_complete_toggles_and_returns_row_partial(self, _weather):
        url = reverse("smart_care:complete", args=[self.task.pk])
        response = self.client.post(url, HTTP_HX_REQUEST="true")
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_completed)
        self.assertTemplateUsed(response, "smart_care/_task_row.html")
        self.assertContains(response, f'id="task-{self.task.pk}"')
        self.assertContains(response, 'hx-swap-oob="true"')
        self.assertContains(response, "1/1 selesai hari ini")

        self.client.post(url, HTTP_HX_REQUEST="true")
        self.task.refresh_from_db()
        self.assertFalse(self.task.is_completed)

    def test_complete_without_htmx_redirects(self, _weather):
        response = self.client.post(reverse("smart_care:complete", args=[self.task.pk]))
        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_completed)
