import requests
from django.conf import settings
from django.shortcuts import render
from .models import CitySearch

def home(request):
    city = request.GET.get("city", "Kochi").strip() or "Kochi"

    context = {
    "city": city,
    "weather": None,
    "forecast": [],
    "error": None,
    "recent_searches": CitySearch.objects.all()[:5],
}

    api_key = settings.WEATHERAPI_KEY

    if not api_key:
        context["error"] = (
            "Weather service is not configured. "
            "Please check the WEATHERAPI_KEY in your .env file."
        )
        return render(request, "weather/index.html", context)

    try:
        response = requests.get(
            "https://api.weatherapi.com/v1/forecast.json",
            params={
                "key": api_key,
                "q": city,
                "days": 3,
                "aqi": "no",
                "alerts": "no",
            },
            timeout=8,
        )

        data = response.json()

        if response.status_code != 200:
            api_error = data.get("error", {})
            error_code = api_error.get("code")

            if error_code == 1006:
                context["error"] = (
                    f"We couldn't find weather for '{city}'. "
                    "Check the spelling and try again."
                )
            elif error_code in (1002, 2006, 2008):
                context["error"] = (
                    "The weather service API key is missing, invalid, "
                    "or disabled. Check your WeatherAPI account and .env file."
                )
            elif error_code == 2007:
                context["error"] = (
                    "The weather service has reached its monthly API limit."
                )
            elif error_code == 2009:
                context["error"] = (
                    "Your WeatherAPI plan does not allow this request."
                )
            else:
                context["error"] = (
                    "The weather service returned an error. Please try again."
                )

            return render(request, "weather/index.html", context)

        location = data["location"]
        current = data["current"]

        context["city"] = location["name"]
        CitySearch.objects.create(
            city=location["name"],
            country=location["country"],
        )

        context["recent_searches"] = CitySearch.objects.all()[:5]

        context["weather"] = {
            "country": location["country"],
            "localtime": location["localtime"],
            "temperature": current["temp_c"],
            "feels_like": current["feelslike_c"],
            "condition": current["condition"]["text"],
            "icon": "https:" + current["condition"]["icon"],
            "humidity": current["humidity"],
            "wind_speed": current["wind_kph"],
            "pressure": current["pressure_mb"],
        }

        forecast_days = data["forecast"]["forecastday"]

        context["forecast"] = [
            {
                "date": day["date"],
                "max_temp": day["day"]["maxtemp_c"],
                "min_temp": day["day"]["mintemp_c"],
                "condition": day["day"]["condition"]["text"],
                "icon": "https:" + day["day"]["condition"]["icon"],
                "chance_of_rain": day["day"]["daily_chance_of_rain"],
                "sunrise": day["astro"]["sunrise"],
                "sunset": day["astro"]["sunset"],
            }
            for day in forecast_days
        ]

    except requests.exceptions.Timeout:
        context["error"] = (
            "The weather service took too long to respond. Please try again."
        )
    except requests.exceptions.RequestException:
        context["error"] = (
            "Could not connect to the weather service. Check your internet connection."
        )
    except (ValueError, KeyError, TypeError):
        context["error"] = (
            "The weather service returned an unexpected response. Please try again."
        )

    return render(request, "weather/index.html", context)
