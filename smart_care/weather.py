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
FORECAST_DAYS = 7  # today and the six days after it
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
PARTLY_CLOUDY_LIMIT = 50  # from this chance (%) a dry day reads "cerah berawan" instead of "cerah"
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
        "forecast_days": FORECAST_DAYS,
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


def _mm_text(mm):
    """A rain total the way it is written in Indonesian: a comma, and no ",0" for whole millimetres."""
    return f"{mm:.1f}".replace(".", ",").removesuffix(",0")


def recommendation(weather, when="hari ini"):
    """One headline for the weather card (a short pill and a sentence); the first matching rule wins.

    `when` is how the day is called in the sentence: "hari ini" for today, "di hari itu" for another day.
    """
    mm = weather.get("rain_mm")
    if is_rainy(weather["rain_probability"], mm):
        return {
            "tone": "rain",
            "pill": "Hujan cukup deras",
            "message": f"Sekitar {_mm_text(mm)} mm {when}. Tanaman outdoor mungkin tidak perlu disiram, cek tanah dulu.",
        }
    if _number(weather["rain_probability"]) >= RAIN_LIMIT:
        amount = f" (sekitar {_mm_text(mm)} mm)" if isinstance(mm, (int, float)) else ""
        return {"tone": "drizzle", "pill": "Hujan ringan", "message": f"Kemungkinan hanya gerimis{amount}. Siram sesuai jadwal."}
    if _number(weather["temperature_max"]) >= HEAT_LIMIT:
        return {"tone": "heat", "pill": "Cuaca panas", "message": f"Cuaca panas {when}. Cek kelembapan media tanam."}
    if _number(weather.get("humidity")) >= HUMIDITY_LIMIT:
        return {"tone": "humid", "pill": "Udara lembap", "message": "Udara sangat lembap. Periksa daun dari tanda jamur."}
    return {"tone": "ok", "pill": "Cuaca aman", "message": "Tidak ada hujan berarti. Waktu yang pas untuk merawat tanaman."}


def task_hints(weather):
    """Hints keyed by task_type; the page shows them only on outdoor tasks that are not done yet."""
    mm = weather.get("rain_mm")
    hints = {}
    if is_rainy(weather["rain_probability"], mm):
        hints["watering"] = f"Hujan sekitar {_mm_text(mm)} mm. Cek tanah dulu, mungkin tidak perlu disiram."
        hints["fertilizing"] = "Pupuk bisa tercuci hujan, tunda dulu."
        hints["repotting"] = "Tanah basah dan mudah berantakan. Pertimbangkan hari lain."
    elif _number(weather["temperature_max"]) >= HEAT_LIMIT:
        hints["watering"] = "Cuaca panas. Siram saat pagi atau sore dan cek kelembapan media."
    return hints


def outlook(weather):
    """How a day looks: the sky of the scene, a short label and the icon of the week strip."""
    if is_rainy(weather["rain_probability"], weather.get("rain_mm")):
        return {"sky": "rain", "label": "Hujan", "icon": "rain"}
    chance = _number(weather["rain_probability"])
    if chance >= RAIN_LIMIT:
        return {"sky": "soft", "label": "Hujan ringan", "icon": "cloud"}
    if chance >= PARTLY_CLOUDY_LIMIT:
        return {"sky": "clear", "label": "Cerah berawan", "icon": "cloudsun"}
    return {"sky": "clear", "label": "Cerah", "icon": "sun"}


def ambient(weather):
    """Which single background effect the weather panel plays: rain, sun or cloud."""
    if is_rainy(weather["rain_probability"], weather.get("rain_mm")):
        return "rain"
    if _number(weather["temperature_max"]) >= HEAT_LIMIT:
        return "sun"
    return "cloud"


def weather_payload(city):
    """Everything the page needs in one JSON-ready dict (thresholds stay here, they are not shown).

    The top-level `recommendation`, `hints` and `ambient` describe today. Every entry of `daily` carries the same
    kind of answer for its own day, so the page can show any day of the week without repeating a rule.
    """
    weather = fetch_weather(city)
    daily = []
    for index, day in enumerate(weather["daily"]):
        # only today has a humidity reading; the forecast has none for the days after it
        view = {**day, "humidity": weather["humidity"] if index == 0 else None}
        daily.append({
            **day,
            "rainy": is_rainy(day["rain_probability"], day.get("rain_mm")),
            "outlook": outlook(view),
            "recommendation": recommendation(view, "hari ini" if index == 0 else "di hari itu"),
            "hints": task_hints(view),
        })
    return {
        "available": True,
        **weather,
        "ambient": ambient(weather),
        "recommendation": recommendation(weather),
        "hints": task_hints(weather),
        "daily": daily,
    }
