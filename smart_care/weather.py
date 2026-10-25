"""Open-Meteo weather lookup (the project's only external API) and the care advice built on it.

Only the standard library is used for the request. All decision rules live here in Python;
the page just renders what `weather_payload` returns.
"""
import json
import logging
from urllib.parse import urlencode
from urllib.request import urlopen

from django.core.cache import cache

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 5
CACHE_SECONDS = 15 * 60
DEFAULT_CITY = "Depok"

# Open-Meteo cuts the days at midnight of this zone, so it has to be the city's own. Only Makassar is WITA (UTC+8);
# the other supported cities are WIB. A city added later outside WIB needs an entry here.
DEFAULT_TIMEZONE = "Asia/Jakarta"
TIMEZONES = {"Makassar": "Asia/Makassar"}

CITIES = {
    "Jakarta": (-6.20, 106.81),
    "Bogor": (-6.59, 106.79),
    "Depok": (-6.40, 106.82),
    "Tangerang": (-6.18, 106.63),
    "Bekasi": (-6.24, 107.00),
    "Bandung": (-6.91, 107.61),
    "Semarang": (-6.97, 110.42),
    "Yogyakarta": (-7.80, 110.36),
    "Surabaya": (-7.25, 112.75),
    "Malang": (-7.98, 112.63),
    "Medan": (3.59, 98.67),
    "Makassar": (-5.15, 119.43),
}

# Thresholds behind every message, also drawn as limit lines on the meters
RAIN_LIMIT = 70
# A day only counts as rainy when the peak chance is high AND this much rain is expected in total. The peak chance
# alone reaches ~100% almost every afternoon in the wet season, even when only a few drops fall.
RAIN_MM_LIMIT = 5
HEAT_LIMIT = 32
HUMIDITY_LIMIT = 85

# WMO weather interpretation codes grouped into short Indonesian labels
CONDITIONS = [
    ({0}, "Cerah"),
    ({1, 2}, "Cerah berawan"),
    ({3}, "Berawan"),
    ({45, 48}, "Berkabut"),
    ({51, 53, 55, 56, 57}, "Gerimis"),
    ({61, 63, 65, 66, 67, 80, 81, 82}, "Hujan"),
    ({95, 96, 99}, "Badai petir"),
]


class WeatherUnavailable(Exception):
    """The API could not be reached or returned something unusable."""


def condition_label(code):
    for codes, label in CONDITIONS:
        if code in codes:
            return label
    return "Berawan"


def fetch_weather(city):
    """Current + daily weather for a supported city. Cached 15 minutes; failures are never cached."""
    if city not in CITIES:
        raise WeatherUnavailable(f"Kota tidak didukung: {city}")

    cache_key = f"smart_care:weather:v2:{city}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    latitude, longitude = CITIES[city]
    query = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
        "daily": "precipitation_probability_max,precipitation_sum,temperature_2m_max",
        "timezone": TIMEZONES.get(city, DEFAULT_TIMEZONE),
        "forecast_days": 7,
    })
    try:
        with urlopen(f"{OPEN_METEO_URL}?{query}", timeout=TIMEOUT_SECONDS) as response:
            payload = json.load(response)
        current = payload["current"]
        daily = payload["daily"]
        # the total is a nice-to-have: without it a day simply never counts as rainy
        totals = daily.get("precipitation_sum") or [None] * len(daily["time"])
        days = [
            {"date": day, "rain_probability": rain, "rain_mm": mm, "temperature_max": hottest}
            for day, rain, mm, hottest in zip(daily["time"], daily["precipitation_probability_max"], totals, daily["temperature_2m_max"])
        ]
        data = {
            "city": city,
            "condition": condition_label(current.get("weather_code")),
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            # today's rain chance, rain total and daily maximum drive the advice rules
            "rain_probability": days[0]["rain_probability"],
            "rain_mm": days[0]["rain_mm"],
            "temperature_max": days[0]["temperature_max"],
            "daily": days,
        }
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        # OSError covers URLError, HTTPError and timeouts; ValueError covers bad JSON
        logger.warning("Open-Meteo request failed for %s: %s", city, exc)
        raise WeatherUnavailable(str(exc)) from exc

    cache.set(cache_key, data, CACHE_SECONDS)
    return data


def _number(value):
    return value if isinstance(value, (int, float)) else 0


def is_rainy(rain_probability, rain_mm):
    """High peak chance AND enough rain in total. A missing number never counts."""
    return _number(rain_probability) >= RAIN_LIMIT and _number(rain_mm) >= RAIN_MM_LIMIT


def recommendation(weather):
    """One headline message; the first matching rule wins."""
    if is_rainy(weather["rain_probability"], weather.get("rain_mm")):
        return {"tone": "rain", "message": "Peluang hujan tinggi hari ini. Cek tanah sebelum menyiram."}
    if _number(weather["temperature_max"]) >= HEAT_LIMIT:
        return {"tone": "heat", "message": "Cuaca panas hari ini. Cek kelembapan media tanam."}
    if _number(weather["humidity"]) >= HUMIDITY_LIMIT:
        return {"tone": "humid", "message": "Udara sangat lembap. Periksa daun dari tanda jamur."}
    return {"tone": "ok", "message": "Cuaca aman untuk merawat tanaman hari ini."}


def task_hints(weather):
    """Hints keyed by task_type; the page shows them only on outdoor tasks that are not done yet."""
    rainy = is_rainy(weather["rain_probability"], weather.get("rain_mm"))
    hot = _number(weather["temperature_max"]) >= HEAT_LIMIT
    hints = {}
    if rainy:
        hints["watering"] = "Peluang hujan tinggi. Cek tanah dulu sebelum menyiram."
        hints["fertilizing"] = "Pupuk bisa tercuci hujan, tunda dulu."
    elif hot:
        hints["watering"] = "Cuaca panas. Siram saat pagi atau sore dan cek kelembapan media."
    return hints


def ambient(weather):
    """Which single background effect the weather panel plays: rain, sun or cloud."""
    if is_rainy(weather["rain_probability"], weather.get("rain_mm")):
        return "rain"
    if _number(weather["temperature_max"]) >= HEAT_LIMIT:
        return "sun"
    return "cloud"


def weather_payload(city):
    """Everything the page needs in one JSON-ready dict (thresholds stay here, they are not shown)."""
    weather = fetch_weather(city)
    return {
        "available": True,
        **weather,
        "ambient": ambient(weather),
        "recommendation": recommendation(weather),
        "hints": task_hints(weather),
        # one entry per forecast day; `rainy` is decided here so the page never repeats the rule
        "daily": [{**day, "rainy": is_rainy(day["rain_probability"], day.get("rain_mm"))} for day in weather["daily"]],
    }
