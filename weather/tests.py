from copy import deepcopy
import requests
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CitySearch


@override_settings(WEATHERAPI_KEY="test-api-key")
class WeatherDashboardTests(TestCase):
    """Tests for the weather dashboard and search history."""

    def setUp(self):
        # Prepare a fake successful weather response.
        self.weather_data = {
            "location": {
                "name": "Kochi",
                "country": "India",
                "localtime": "2026-10-19 14:00",
            },
            "current": {
                "temp_c": 30.0,
                "feelslike_c": 34.0,
                "condition": {
                    "text": "Partly cloudy",
                    "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png",
                },
                "humidity": 75,
                "wind_kph": 12.0,
                "pressure_mb": 1010.0,
            },
            "forecast": {
                "forecastday": [
                    {
                        "date": "2026-10-19",
                        "day": {
                            "maxtemp_c": 31.0,
                            "mintemp_c": 25.0,
                            "condition": {
                                "text": "Partly cloudy",
                                "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png",
                            },
                            "daily_chance_of_rain": 30,
                        },
                        "astro": {
                            "sunrise": "06:10 AM",
                            "sunset": "06:05 PM",
                        },
                    },
                    {
                        "date": "2026-10-20",
                        "day": {
                            "maxtemp_c": 32.0,
                            "mintemp_c": 25.0,
                            "condition": {
                                "text": "Sunny",
                                "icon": "//cdn.weatherapi.com/weather/64x64/day/113.png",
                            },
                            "daily_chance_of_rain": 10,
                        },
                        "astro": {
                            "sunrise": "06:10 AM",
                            "sunset": "06:05 PM",
                        },
                    },
                    {
                        "date": "2026-10-21",
                        "day": {
                            "maxtemp_c": 30.0,
                            "mintemp_c": 24.0,
                            "condition": {
                                "text": "Light rain",
                                "icon": "//cdn.weatherapi.com/weather/64x64/day/296.png",
                            },
                            "daily_chance_of_rain": 60,
                        },
                        "astro": {
                            "sunrise": "06:10 AM",
                            "sunset": "06:05 PM",
                        },
                    },
                ]
            },
        }

    def mock_weather_success(self):
        """Return a fake successful HTTP response."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = self.weather_data
        return response

    @patch("weather.views.requests.get")
    def test_home_displays_current_weather_and_forecast(self, mock_get):
        mock_get.return_value = self.mock_weather_success()

        response = self.client.get("/", {"city": "Kochi"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kochi")
        self.assertContains(response, "Partly cloudy")
        self.assertEqual(len(response.context["forecast"]), 3)
        self.assertEqual(response.context["weather"]["temperature"], 30.0)

    @patch("weather.views.requests.get")
    def test_successful_search_is_saved(self, mock_get):
        mock_get.return_value = self.mock_weather_success()

        self.client.get("/", {"city": "Kochi"})

        self.assertEqual(CitySearch.objects.count(), 1)
        saved_search = CitySearch.objects.first()
        self.assertEqual(saved_search.city, "Kochi")
        self.assertEqual(saved_search.country, "India")
        self.assertIsNotNone(saved_search.searched_at)

    @patch("weather.views.requests.get")
    def test_invalid_city_is_not_saved(self, mock_get):
        response_mock = Mock()
        response_mock.status_code = 400
        response_mock.json.return_value = {
            "error": {
                "code": 1006,
                "message": "No matching location found."
            }
        }
        mock_get.return_value = response_mock

        response = self.client.get("/", {"city": "Xyznotacity123"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Check the spelling and try again.")
        self.assertEqual(CitySearch.objects.count(), 0)

    @patch("weather.views.requests.get")
    def test_api_timeout_shows_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout

        response = self.client.get("/", {"city": "Kochi"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "too long to respond")
        self.assertEqual(CitySearch.objects.count(), 0)

    @patch("weather.views.requests.get")
    def test_connection_error_shows_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError

        response = self.client.get("/", {"city": "Kochi"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Could not connect")
        self.assertEqual(CitySearch.objects.count(), 0)

    
    @patch("weather.views.requests.get")
    def test_only_five_most_recent_searches_are_displayed(self, mock_get):
        def fake_weather_response(*args, **kwargs):
            city = kwargs["params"]["q"]
            data = deepcopy(self.weather_data)
            data["location"]["name"] = city

            response = Mock()
            response.status_code = 200
            response.json.return_value = data
            return response

        mock_get.side_effect = fake_weather_response

        cities = [
            "Kochi",
            "Thrissur",
            "Chennai",
            "Mumbai",
            "Delhi",
            "Bengaluru",
        ]

        for city in cities:
            response = self.client.get("/", {"city": city})
            self.assertEqual(response.status_code, 200)

        self.assertEqual(CitySearch.objects.count(), 6)

        recent_searches = response.context["recent_searches"]
        recent_cities = [search.city for search in recent_searches]

        self.assertEqual(len(recent_cities), 5)
        self.assertEqual(recent_cities[0], "Bengaluru")
        self.assertNotIn("Kochi", recent_cities)


    @patch("weather.views.requests.get")
    def test_recent_city_link_is_rendered(self, mock_get):
        mock_get.return_value = self.mock_weather_success()

        self.client.get("/", {"city": "Kochi"})
        response = self.client.get("/")

        self.assertContains(response, "Recently searched")
        self.assertContains(response, "Kochi, India")
        self.assertContains(response, "city=Kochi")
