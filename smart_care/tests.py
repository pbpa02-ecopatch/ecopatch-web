import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from django.core.cache import cache
from django.test import TestCase

from . import weather as weather_module
from .weather import WeatherUnavailable, ambient, fetch_weather, recommendation, task_hints, weather_payload

API_RESPONSE = {
    "current": {"temperature_2m": 29.4, "relative_humidity_2m": 80, "precipitation": 0.2, "weather_code": 61},
    "daily": {
        "time": [f"2026-10-{24 + i}" for i in range(7)],
        "precipitation_probability_max": [75, 40, 10, 0, 70, 20, 5],
        "temperature_2m_max": [31.2, 32.5, 30.0, 29.1, 28.4, 33.0, 31.9],
    },
}


def fake_response(payload):
    """Stand-in for the object `urlopen` returns (a context manager with a readable body)."""
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps(payload).encode()
    return response


def weather_data(**overrides):
    data = {
        "city": "Depok",
        "condition": "Hujan",
        "temperature": 29.4,
        "humidity": 80,
        "precipitation": 0.2,
        "rain_probability": 20,
        "temperature_max": 30,
        "daily": [
            {"date": "2026-10-24", "rain_probability": 20, "temperature_max": 30},
            {"date": "2026-10-25", "rain_probability": 85, "temperature_max": 29},
        ],
    }
    data.update(overrides)
    return data


class WeatherTestCase(TestCase):
    def setUp(self):
        cache.clear()


class FetchWeatherTests(WeatherTestCase):
    @patch("smart_care.weather.urlopen")
    def test_parses_open_meteo_response(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(API_RESPONSE)
        data = fetch_weather("Depok")
        self.assertEqual(data["temperature"], 29.4)
        self.assertEqual(data["humidity"], 80)
        self.assertEqual(data["rain_probability"], 75)
        self.assertEqual(data["temperature_max"], 31.2)
        self.assertEqual(data["condition"], "Hujan")
        self.assertEqual(len(data["daily"]), 7)
        self.assertEqual(data["daily"][1], {"date": "2026-10-25", "rain_probability": 40, "temperature_max": 32.5})
        url = mock_urlopen.call_args.args[0]
        self.assertIn("precipitation_probability_max", url)
        self.assertIn("forecast_days=7", url)
        self.assertIn("timezone=Asia%2FJakarta", url)
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 5)

    @patch("smart_care.weather.urlopen")
    def test_result_is_cached_per_city(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(API_RESPONSE)
        fetch_weather("Depok")
        fetch_weather("Depok")
        self.assertEqual(mock_urlopen.call_count, 1)
        fetch_weather("Bogor")
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("smart_care.weather.urlopen", side_effect=URLError("offline"))
    def test_network_error_raises_and_is_not_cached(self, mock_urlopen):
        with self.assertRaises(WeatherUnavailable):
            fetch_weather("Depok")
        with self.assertRaises(WeatherUnavailable):
            fetch_weather("Depok")
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("smart_care.weather.urlopen")
    def test_malformed_payload_raises(self, mock_urlopen):
        mock_urlopen.return_value = fake_response({"current": {}})
        with self.assertRaises(WeatherUnavailable):
            fetch_weather("Depok")

    @patch("smart_care.weather.urlopen")
    def test_unknown_city_never_calls_the_api(self, mock_urlopen):
        with self.assertRaises(WeatherUnavailable):
            fetch_weather("Atlantis")
        mock_urlopen.assert_not_called()

    def test_all_twelve_cities_are_supported(self):
        self.assertEqual(len(weather_module.CITIES), 12)


class RecommendationTests(TestCase):
    def test_high_rain_probability(self):
        result = recommendation(weather_data(rain_probability=70))
        self.assertEqual(result["tone"], "rain")
        self.assertEqual(result["message"], "Peluang hujan tinggi hari ini. Cek tanah sebelum menyiram.")

    def test_heat_uses_the_daily_maximum(self):
        result = recommendation(weather_data(temperature=25, temperature_max=32))
        self.assertEqual(result["tone"], "heat")
        self.assertEqual(result["message"], "Cuaca panas hari ini. Cek kelembapan media tanam.")

    def test_high_humidity_warns_about_fungus(self):
        result = recommendation(weather_data(humidity=85))
        self.assertEqual(result["tone"], "humid")
        self.assertIn("jamur", result["message"])

    def test_safe_weather(self):
        self.assertEqual(recommendation(weather_data())["tone"], "ok")

    def test_rain_beats_heat_and_humidity(self):
        result = recommendation(weather_data(rain_probability=90, temperature_max=35, humidity=95))
        self.assertEqual(result["tone"], "rain")

    def test_just_below_every_threshold_is_safe(self):
        result = recommendation(weather_data(rain_probability=69, temperature_max=31.9, humidity=84))
        self.assertEqual(result["tone"], "ok")

    def test_missing_values_do_not_break_the_rules(self):
        result = recommendation(weather_data(rain_probability=None, temperature_max=None, humidity=None))
        self.assertEqual(result["tone"], "ok")


class TaskHintTests(TestCase):
    def test_rain_hints_for_watering_and_fertilizing(self):
        hints = task_hints(weather_data(rain_probability=80))
        self.assertIn("Cek tanah", hints["watering"])
        self.assertEqual(hints["fertilizing"], "Pupuk bisa tercuci hujan, tunda dulu.")

    def test_heat_hint_only_for_watering(self):
        hints = task_hints(weather_data(temperature_max=33))
        self.assertIn("watering", hints)
        self.assertNotIn("fertilizing", hints)

    def test_no_hints_in_safe_weather(self):
        self.assertEqual(task_hints(weather_data()), {})

    def test_ambient_effect_is_one_at_a_time(self):
        self.assertEqual(ambient(weather_data(rain_probability=80, temperature_max=35)), "rain")
        self.assertEqual(ambient(weather_data(temperature_max=33)), "sun")
        self.assertEqual(ambient(weather_data()), "cloud")

    def test_payload_carries_a_week_of_forecast_with_the_rain_rule_applied(self):
        with patch("smart_care.weather.fetch_weather", return_value=weather_data(rain_probability=75)):
            payload = weather_payload("Depok")
        self.assertEqual([day["rainy"] for day in payload["daily"]], [False, True])
        self.assertEqual(payload["recommendation"]["tone"], "rain")
        self.assertEqual(payload["ambient"], "rain")
        self.assertNotIn("meters", payload)  # thresholds are not exposed to the page

    def test_seventy_percent_counts_as_a_rainy_day(self):
        days = [{"date": "2026-10-24", "rain_probability": 70, "temperature_max": 30},
                {"date": "2026-10-25", "rain_probability": 69, "temperature_max": 30}]
        with patch("smart_care.weather.fetch_weather", return_value=weather_data(daily=days)):
            payload = weather_payload("Depok")
        self.assertEqual([day["rainy"] for day in payload["daily"]], [True, False])
