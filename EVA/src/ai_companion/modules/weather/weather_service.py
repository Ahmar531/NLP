import logging
import re
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("ai_companion.weather")

# WMO Weather interpretation codes (WW) from Open-Meteo
WMO_CODE_MAP: Dict[int, str] = {
    0: "Clear sky / Sunny",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    62: "Moderate rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm (slight or moderate)",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# Common Pakistani cities for rapid regex extraction
COMMON_PAKISTAN_CITIES = [
    "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad",
    "peshawar", "quetta", "multan", "sialkot", "gujranwala",
    "hyderabad", "abbottabad", "murree", "gilgit", "skardu",
    "gwadar", "bahawalpur", "sargodha", "sukkur", "larkana",
    "sheikhupura", "jhang", "gujrat", "mardan", "kasur",
    "rahim yar khan", "sahiwal", "okara", "wah cantt", "dera ghazi khan",
    "mirpur", "muzaffarabad", "swat", "chitral", "hunza",
]

# Weather query keywords in English and Urdu/Roman Urdu
WEATHER_KEYWORDS = [
    "weather", "temperature", "forecast", "climate", "temp",
    "rain", "raining", "rainy", "sunny", "hot", "cold", "humidity",
    "wind", "windy", "storm", "stormy", "snow", "snowing", "cloudy",
    "clouds", "degree", "celsius", "fahrenheit", "precipitation",
    # Urdu / Roman Urdu / Hindi
    "mausam", "mosam", "mousam", "barish", "baarish", "garmi", "sardi",
    "thand", "dhoop", "badal", "baadal", "hawa", "toofan", "tufan",
    "kitni garmi", "kitni thand", "temperature kitna", "barish hogi",
    "mosam kaisa", "mausam kaisa", "mausam kaisa hai", "mosam kaisa hai",
]


def is_weather_query(text: str) -> bool:
    """Detect whether the user's message is asking about weather, temperature, or forecast."""
    if not text or not text.strip():
        return False
    lower_text = text.lower()
    for kw in WEATHER_KEYWORDS:
        # Match as whole word or multi-word phrase
        if " " in kw:
            if kw in lower_text:
                return True
        else:
            if re.search(r"\b" + re.escape(kw) + r"\b", lower_text):
                return True
    return False


def extract_location(text: str, memory_context: str = "") -> str:
    """
    Extract target location/city from user message or fall back to user's stored memory context.
    Defaults to 'Karachi, Pakistan' if no location is specified.
    """
    lower_text = text.lower() if text else ""
    stop_words = {
        "today", "tomorrow", "now", "tonight", "this", "the", "a", "an",
        "kaisa", "hai", "aaj", "kal", "parson", "yahan", "wahan",
        "abhi", "mera", "meri", "apka", "tumhara", "din", "raat", "subah", "shaam",
    }

    # 1. Direct match for known Pakistani cities in message
    for city in COMMON_PAKISTAN_CITIES:
        # Match as whole word
        pattern = r"\b" + re.escape(city) + r"\b"
        if re.search(pattern, lower_text):
            return city.title()

    # 2. General regex match for patterns like "in <City>", "at <City>", "of <City>", "mein <City>", "ka mausam"
    location_patterns = [
        r"(?:weather|temperature|forecast|mausam|mosam)\s+(?:in|at|of|for)\s+([a-zA-Z\s]{2,25})",
        r"(?:in|at)\s+([a-zA-Z]{2,20})\s+(?:weather|temperature|mausam|mosam)",
        r"([a-zA-Z]{2,20})\s+(?:ka|mein|mai|me)\s+(?:mausam|mosam|temperature|barish|weather)",
    ]
    for pat in location_patterns:
        match = re.search(pat, lower_text)
        if match:
            extracted = match.group(1).strip().lower()
            # Filter out non-location stop words
            if extracted and extracted not in stop_words:
                return extracted.title()

    # 3. Check memory context for stored location (e.g., "Lives in Lahore", "Location: Islamabad")
    if memory_context:
        mem_lower = memory_context.lower()
        for city in COMMON_PAKISTAN_CITIES:
            if city in mem_lower:
                return city.title()

        mem_patterns = [
            r"(?:lives in|living in|located in|from|city|location)\s*(?:is|:)?\s*([a-zA-Z\s]{2,25})",
        ]
        for pat in mem_patterns:
            match = re.search(pat, memory_context, re.IGNORECASE)
            if match:
                city_cand = match.group(1).strip().split("\n")[0].split(";")[0].split(".")[0].strip()
                if city_cand and len(city_cand) < 30:
                    return city_cand.title()

    # 4. Default to Karachi, Pakistan
    return "Karachi, Pakistan"


class WeatherService:
    """Asynchronous client for fetching real-time weather and forecasts via Open-Meteo."""

    def __init__(self, timeout_seconds: float = 8.0):
        self.timeout = timeout_seconds

    async def get_coordinates(self, location_name: str) -> Optional[Dict[str, Any]]:
        """Geocode a city or location name to latitude and longitude."""
        clean_name = location_name.split(",")[0].strip()
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {
            "name": clean_name,
            "count": 1,
            "language": "en",
            "format": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    if results:
                        best = results[0]
                        return {
                            "name": best.get("name", clean_name),
                            "country": best.get("country", "Pakistan"),
                            "latitude": best.get("latitude"),
                            "longitude": best.get("longitude"),
                            "timezone": best.get("timezone", "Asia/Karachi"),
                        }
        except Exception as err:
            logger.warning("Geocoding failed for '%s': %s", location_name, err)

        # Fallback to Karachi coordinates if geocoding fails
        if "karachi" in clean_name.lower():
            return {
                "name": "Karachi",
                "country": "Pakistan",
                "latitude": 24.8607,
                "longitude": 67.0011,
                "timezone": "Asia/Karachi",
            }
        elif "lahore" in clean_name.lower():
            return {
                "name": "Lahore",
                "country": "Pakistan",
                "latitude": 31.5497,
                "longitude": 74.3436,
                "timezone": "Asia/Karachi",
            }
        elif "islamabad" in clean_name.lower():
            return {
                "name": "Islamabad",
                "country": "Pakistan",
                "latitude": 33.6844,
                "longitude": 73.0479,
                "timezone": "Asia/Karachi",
            }

        return None

    async def get_weather(self, location_name: str) -> Optional[Dict[str, Any]]:
        """Fetch current weather and 3-day forecast for a given location."""
        coords = await self.get_coordinates(location_name)
        if not coords:
            # Fallback to Karachi default
            coords = {
                "name": "Karachi",
                "country": "Pakistan",
                "latitude": 24.8607,
                "longitude": 67.0011,
                "timezone": "Asia/Karachi",
            }

        lat = coords["latitude"]
        lon = coords["longitude"]
        tz = coords.get("timezone", "auto")

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": tz,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    logger.error("Open-Meteo forecast failed [%d]: %s", response.status_code, response.text)
                    return None

                data = response.json()
                current = data.get("current", {})
                daily = data.get("daily", {})

                # Parse current conditions
                wcode = current.get("weather_code", 0)
                condition_desc = WMO_CODE_MAP.get(wcode, "Clear")
                temp = current.get("temperature_2m", 0.0)
                feels_like = current.get("apparent_temperature", temp)
                humidity = current.get("relative_humidity_2m", 0)
                wind_speed = current.get("wind_speed_10m", 0.0)
                precip = current.get("precipitation", 0.0)

                # Parse daily forecast (up to 3 days)
                forecast_list = []
                dates = daily.get("time", [])
                max_temps = daily.get("temperature_2m_max", [])
                min_temps = daily.get("temperature_2m_min", [])
                daily_codes = daily.get("weather_code", [])
                rain_probs = daily.get("precipitation_probability_max", [])

                for i in range(min(len(dates), 3)):
                    fc_code = daily_codes[i] if i < len(daily_codes) else 0
                    fc_desc = WMO_CODE_MAP.get(fc_code, "Clear")
                    forecast_list.append({
                        "date": dates[i],
                        "max_temp": max_temps[i] if i < len(max_temps) else temp,
                        "min_temp": min_temps[i] if i < len(min_temps) else temp,
                        "condition": fc_desc,
                        "rain_probability": rain_probs[i] if i < len(rain_probs) else 0,
                    })

                return {
                    "location": f"{coords['name']}, {coords['country']}",
                    "timezone": tz,
                    "current": {
                        "temperature": round(float(temp), 1),
                        "feels_like": round(float(feels_like), 1),
                        "condition": condition_desc,
                        "humidity": humidity,
                        "wind_speed": round(float(wind_speed), 1),
                        "precipitation": precip,
                    },
                    "daily_forecast": forecast_list,
                }
        except Exception as err:
            logger.error("Failed to fetch weather from Open-Meteo: %s", err, exc_info=True)
            return None

    def format_weather_context(self, weather_data: Optional[Dict[str, Any]]) -> str:
        """Format weather data into clear, anti-hallucination prompt context distinguishing current vs forecast."""
        if not weather_data:
            return "Real-time weather data is temporarily unavailable. If asked about the weather, inform the user casually that you couldn't check the live update right now."

        loc = weather_data.get("location", "Pakistan")
        cur = weather_data.get("current", {})
        forecasts = weather_data.get("daily_forecast", [])

        lines = [
            f"Location: {loc} (Timezone: {weather_data.get('timezone', 'Asia/Karachi')})",
            "",
            "CURRENT LIVE CONDITIONS (RIGHT NOW):",
            f"- Temperature: {cur.get('temperature')}°C (Feels like: {cur.get('feels_like')}°C)",
            f"- Condition: {cur.get('condition')}",
            f"- Humidity: {cur.get('humidity')}%",
            f"- Wind Speed: {cur.get('wind_speed')} km/h",
            f"- Precipitation: {cur.get('precipitation')} mm",
        ]

        if forecasts:
            lines.append("")
            lines.append("UPCOMING FORECAST:")
            for fc in forecasts:
                lines.append(
                    f"- {fc['date']}: High {fc['max_temp']}°C / Low {fc['min_temp']}°C, {fc['condition']}, Rain Chance: {fc['rain_probability']}%"
                )

        lines.append("")
        lines.append("CRITICAL INSTRUCTION: Use ONLY these exact numbers and conditions. Clearly distinguish between current conditions (right now) and upcoming forecast (future). NEVER make up or guess weather.")

        return "\n".join(lines)


# Global singleton instance
weather_service = WeatherService()
