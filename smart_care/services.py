"""Open-Meteo weather lookup and simple care recommendations for Smart Care."""
import logging

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 5

CITY_COORDINATES = {
    "Jakarta": (-6.20, 106.81), "Bogor": (-6.59, 106.79),
    "Depok": (-6.40, 106.82), "Tangerang": (-6.18, 106.63),
    "Bekasi": (-6.24, 107.00), "Bandung": (-6.91, 107.61),
    "Semarang": (-6.97, 110.42), "Yogyakarta": (-7.80, 110.36),
    "Surabaya": (-7.25, 112.75), "Malang": (-7.98, 112.63),
    "Medan": (3.59, 98.67), "Makassar": (-5.15, 119.43),
}

# WMO weather interpretation codes used by Open-Meteo, grouped into short labels
WEATHER_CONDITIONS = [
    ({0}, "Clear"),
    ({1, 2}, "Partly cloudy"),
    ({3}, "Cloudy"),
    ({45, 48}, "Foggy"),
    ({51, 53, 55, 56, 57}, "Drizzle"),
    ({61, 63, 65, 66, 67, 80, 81, 82}, "Rain"),
    ({95, 96, 99}, "Thunderstorm"),
]


def _condition_label(code):
    for codes, label in WEATHER_CONDITIONS:
        if code in codes:
            return label
    return None


def _unavailable(city):
    return {
        "city": city,
        "available": False,
        "temperature": None,
        "humidity": None,
        "rain_probability": None,
        "condition": None,
    }


def get_weather(city: str) -> dict:
    """Return current weather for a supported city, or an all-None fallback if the API fails."""
    coordinates = CITY_COORDINATES.get(city)
    if coordinates is None:
        return _unavailable(city)

    latitude, longitude = coordinates
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation_probability,weather_code",
        "timezone": "auto",
    }
    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        current = response.json()["current"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        logger.warning("Open-Meteo request failed for %s", city, exc_info=True)
        return _unavailable(city)

    return {
        "city": city,
        "available": True,
        "temperature": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "rain_probability": current.get("precipitation_probability"),
        "condition": _condition_label(current.get("weather_code")),
    }


def get_recommendation(weather: dict) -> str | None:
    # `or 0` keeps the fallback dict (values are None) from breaking the comparisons
    if (weather.get("rain_probability") or 0) >= 70:
        return "High chance of rain today. Check soil condition before watering."
    if (weather.get("temperature") or 0) >= 32:
        return "Hot weather today. Check your plants' moisture."
    return None
