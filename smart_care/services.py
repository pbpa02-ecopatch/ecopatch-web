import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

CITY_COORDINATES = {
    "Jakarta": (-6.2088, 106.8456),
    "Bogor": (-6.5971, 106.8060),
    "Depok": (-6.4025, 106.7942),
    "Tangerang": (-6.1783, 106.6319),
    "Bekasi": (-6.2383, 106.9756),
    "Bandung": (-6.9175, 107.6191),
    "Semarang": (-6.9667, 110.4167),
    "Yogyakarta": (-7.7956, 110.3695),
    "Surabaya": (-7.2575, 112.7521),
    "Malang": (-7.9666, 112.6326),
    "Medan": (3.5952, 98.6722),
    "Makassar": (-5.1477, 119.4327),
}

DEFAULT_CITY = "Jakarta"


def get_weather_data(city):
    """Fetch current weather for a supported city from Open-Meteo.

    Returns a dict with temperature, humidity, precipitation and
    rain_probability, or None if the city is unknown or the request fails.
    """
    coordinates = CITY_COORDINATES.get(city)
    if coordinates is None:
        return None

    latitude, longitude = coordinates
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation",
        "hourly": "precipitation_probability",
        "timezone": "Asia/Jakarta",
    }

    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    current = data.get("current", {})
    hourly = data.get("hourly", {})
    rain_probabilities = hourly.get("precipitation_probability") or []

    return {
        "city": city,
        "temperature": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "precipitation": current.get("precipitation"),
        "rain_probability": rain_probabilities[0] if rain_probabilities else None,
    }


def get_care_recommendation(weather):
    """Build simple recommendation messages from a weather dict."""
    if not weather:
        return []

    messages = []
    rain_probability = weather.get("rain_probability")
    temperature = weather.get("temperature")

    if rain_probability is not None and rain_probability >= 70:
        messages.append("High chance of rain today. Check soil condition before watering.")

    if temperature is not None and temperature >= 32:
        messages.append("Hot weather today. Check your plants' moisture.")

    return messages
