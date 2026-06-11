"""get_weather tool (Tier 0) backed by Open-Meteo — free, no API key.

Also drives the weather wardrobe (spec §9): current_conditions() returns the
small structured snapshot the daemon maps to overlays on a schedule.
"""

import logging

import requests

log = logging.getLogger("vato.weather")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Weather-code groups for the wardrobe (Open-Meteo WMO codes)
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}
SNOW_CODES = {71, 73, 75, 77, 85, 86}
CLEAR_CODES = {0, 1}

WEATHER_CODES = {
    0: "clear skies", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "heavy freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "heavy freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "violent showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "a thunderstorm", 96: "a thunderstorm with hail",
    99: "a severe thunderstorm with hail",
}


class WeatherService:
    def __init__(self, cfg: dict):
        loc = cfg.get("location", {})
        self._home_name = loc.get("name") or "home"
        self._home_lat = loc.get("latitude")
        self._home_lon = loc.get("longitude")
        self._fahrenheit = (loc.get("units", "fahrenheit") or "").lower() != "celsius"
        self._home_coords: tuple[float, float] | None = None  # geocode cache

    def _geocode(self, name: str) -> tuple[float, float, str]:
        resp = requests.get(GEOCODE_URL, params={"name": name, "count": 1}, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            raise ValueError(f"Could not find a place called {name!r}")
        hit = results[0]
        return hit["latitude"], hit["longitude"], hit["name"]

    def get_weather(self, location: str | None = None) -> str:
        if location:
            lat, lon, place = self._geocode(location)
        elif self._home_lat is not None and self._home_lon is not None:
            lat, lon, place = self._home_lat, self._home_lon, self._home_name
        else:
            lat, lon, place = self._geocode(self._home_name)

        unit = "fahrenheit" if self._fahrenheit else "celsius"
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,weather_code,"
                           "wind_speed_10m,relative_humidity_2m",
                "daily": "temperature_2m_max,temperature_2m_min,"
                         "precipitation_probability_max",
                "temperature_unit": unit,
                "wind_speed_unit": "mph" if self._fahrenheit else "kmh",
                "timezone": "auto",
                "forecast_days": 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        cur = data["current"]
        day = data["daily"]
        deg = "°F" if self._fahrenheit else "°C"
        wind_unit = "mph" if self._fahrenheit else "km/h"
        condition = WEATHER_CODES.get(cur["weather_code"], "unsettled conditions")

        return (
            f"Weather in {place}: {condition}, {round(cur['temperature_2m'])}{deg} "
            f"(feels like {round(cur['apparent_temperature'])}{deg}), "
            f"humidity {cur['relative_humidity_2m']}%, "
            f"wind {round(cur['wind_speed_10m'])} {wind_unit}. "
            f"Today: high {round(day['temperature_2m_max'][0])}{deg}, "
            f"low {round(day['temperature_2m_min'][0])}{deg}, "
            f"chance of precipitation {day['precipitation_probability_max'][0]}%."
        )


    def _home(self) -> tuple[float, float]:
        if self._home_coords is None:
            if self._home_lat is not None and self._home_lon is not None:
                self._home_coords = (self._home_lat, self._home_lon)
            else:
                lat, lon, _ = self._geocode(self._home_name)
                self._home_coords = (lat, lon)
        return self._home_coords

    def current_conditions(self) -> dict:
        """Structured snapshot for the wardrobe: temp in °C (unit-independent
        thresholds), WMO weather code, and whether the sun is up."""
        lat, lon = self._home()
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,is_day",
                "temperature_unit": "celsius",
                "timezone": "auto",
            },
            timeout=10,
        )
        resp.raise_for_status()
        cur = resp.json()["current"]
        return {
            "temp_c": float(cur["temperature_2m"]),
            "code": int(cur["weather_code"]),
            "is_day": bool(cur["is_day"]),
        }


GET_WEATHER_SCHEMA = {
    "type": "object",
    "properties": {
        "location": {
            "type": "string",
            "description": "City or place name. Omit for the household's home location.",
        }
    },
    "required": [],
}
