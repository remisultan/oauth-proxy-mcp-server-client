import datetime
from typing import Any
from urllib.parse import quote

import requests
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError


def register(mcp):
    def get_user_claims(ctx: Context):
        return ctx.request_context.request.user.access_token.claims

    @mcp.tool()
    async def get_time(ctx: Context) -> dict[str, Any]:
        """
        Return current server time (protected by OAuth).
        """
        claims = get_user_claims(ctx)
        if "graviteesource.com" in claims['email']:
            now = datetime.datetime.now()
            return {
                "current_time": now.isoformat(),
                "timezone": "UTC",
                "timestamp": now.timestamp(),
                "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
            }
        else:
            raise ToolError("403", "Forbidden", "Cannot get time sorry!")

    @mcp.tool()
    def search_locations(query: str, ctx: Context) -> dict[str, Any]:
        """
        Search for a location (place, address, or city) using a text query.

        Args:
            query: The search string (e.g., "Eiffel Tower", "Tokyo").

        Returns:
            A list of dictionaries, each with 'name', 'city', and 'country'.
        """
        claims = get_user_claims(ctx)

        if "graviteesource.com" in claims['email']:
            url = "https://photon.komoot.io/api"
            params = {"q": quote(query), "limit": 5}

            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                results = []
                for feature in data.get("features", []):
                    props = feature.get("properties", {})
                    results.append({
                        "name": props.get("name"),
                        "city": props.get("city"),
                        "country": props.get("country"),
                        "location": f"{props.get('extent', [])[0]},{props.get('extent', [])[1]}"
                    })
                return results
            except requests.exceptions.RequestException as e:
                raise ToolError(f"An error occurred while searching for locations: {e}")
        else:
            raise ToolError("403", "Forbidden", "Cannot get time sorry!")

    @mcp.tool()
    def get_weather_forecast(location: str, ctx: Context) -> dict:
        """
        Gets the daily weather forecast for a location on a specific date.

        Args:
            location: The location coordinates (e.g., "48.8584,2.2945").

        Returns:
            A dictionary with the weather forecast summary.
        """
        claims = get_user_claims(ctx)
        if "graviteesource.com" in claims['email']:
            return weather_forecast(location)
        else:
            raise ToolError("403", "Forbidden", "Cannot get time sorry!")

    def weather_forecast(location):
        try:
            lat, lon = location.split(',')
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                "start_date": "2025-09-17",
                "end_date": "2025-09-17"
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            daily_data = data.get("daily", {})
            weather_code = daily_data['weather_code'][0]
            temp_max = daily_data['temperature_2m_max'][0]
            temp_min = daily_data['temperature_2m_min'][0]
            precipitation = daily_data['precipitation_sum'][0]
            wind_speed = daily_data['wind_speed_10m_max'][0]

            return {
                "weather_code": weather_code,
                "max_temp_celsius": temp_max,
                "min_temp_celsius": temp_min,
                "precipitation_mm": precipitation,
                "max_wind_speed_kmh": wind_speed
            }
        except requests.exceptions.RequestException as e:
            raise ToolError(f"An error occurred while fetching weather data: {e}")
        except (IndexError, ValueError):
            raise ToolError("Invalid location or date format")

    @mcp.tool()
    async def get_user_profile(ctx: Context) -> dict[str, Any]:
        """Return current server time (protected by OAuth)."""
        return get_user_claims(ctx)
