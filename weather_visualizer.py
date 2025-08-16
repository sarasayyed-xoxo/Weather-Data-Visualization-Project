#!/usr/bin/env python3
import os
import sys
import argparse
from typing import Optional, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import pandas as pd
import matplotlib

# Use a non-interactive backend if running headless
if os.environ.get("DISPLAY", "") == "":
	matplotlib.use("Agg")

import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timezone


class WeatherVisualizer:
	"""
	A class to fetch weather data from OpenWeatherMap, process it,
	and create a visually appealing dashboard.
	"""

	def __init__(self, api_key: str, request_timeout: float = 10.0):
		"""
		Initializes the WeatherVisualizer with the API key.

		Args:
			api_key (str): Your OpenWeatherMap API key.
			request_timeout (float): Timeout in seconds for HTTP requests.
		"""
		if not api_key or api_key.strip().upper() in {"YOUR_API_KEY", ""}:
			raise ValueError(
				"Missing OpenWeatherMap API key. Provide via --api-key or OPENWEATHER_API_KEY env var."
			)
		self.api_key = api_key
		self.base_url = "https://api.openweathermap.org/data/2.5/forecast"
		self.timeout = request_timeout

		# Configure a session with retries for transient errors
		self.session = requests.Session()
		retries = Retry(
			total=3,
			backoff_factor=0.5,
			status_forcelist=[429, 500, 502, 503, 504],
			allowed_methods=["GET"],
		)
		adapter = HTTPAdapter(max_retries=retries)
		self.session.mount("https://", adapter)
		self.session.mount("http://", adapter)

	def fetch_data(self, city: str) -> Optional[Dict[str, Any]]:
		"""
		Fetches 5-day/3-hour forecast data for a given city.

		Args:
			city (str): The name of the city.

		Returns:
			Optional[dict]: The JSON response from the API, or None if an error occurs.
		"""
		params = {"q": city, "appid": self.api_key, "units": "metric"}
		try:
			resp = self.session.get(self.base_url, params=params, timeout=self.timeout)
			resp.raise_for_status()
			return resp.json()
		except requests.exceptions.HTTPError as e:
			status = e.response.status_code if e.response is not None else None
			if status == 404:
				print(f"Error: City '{city}' not found. Please check the spelling and try again.")
			elif status == 401:
				print("Error: Invalid API key. Please check your OpenWeatherMap API key.")
			elif status == 429:
				print("Error: Rate limit exceeded. Please wait and try again.")
			else:
				print(f"An HTTP error occurred: {e}")
			return None
		except requests.exceptions.RequestException as e:
			print(f"A network error occurred: {e}")
			return None

	def process_data(self, data: Dict[str, Any]) -> Optional[pd.DataFrame]:
		"""
		Processes the raw JSON data into a clean pandas DataFrame.

		Args:
			data (dict): The JSON data from the API.

		Returns:
			Optional[pandas.DataFrame]: A DataFrame with structured weather information.
		"""
		if not data or "list" not in data:
			return None

		forecast_list = []
		for item in data.get("list", []):
			try:
				dt_utc = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
				main = item.get("main", {})
				wind = item.get("wind", {})
				weather_arr = item.get("weather", [])
				description = (
					weather_arr[0].get("description", "") if weather_arr else ""
				).title()
				forecast_list.append(
					{
						"datetime": pd.to_datetime(dt_utc),
						"temperature": main.get("temp"),
						"feels_like": main.get("feels_like"),
						"humidity": main.get("humidity"),
						"wind_speed": wind.get("speed"),
						"weather_description": description,
					}
				)
			except Exception:
				continue

		if not forecast_list:
			return None

		df = pd.DataFrame(forecast_list)
		df.sort_values("datetime", inplace=True)
		df.reset_index(drop=True, inplace=True)
		return df

	def create_dashboard(self, df: pd.DataFrame, city: str, save_path: Optional[str] = None, show: bool = True):
		"""
		Creates a beautiful and informative weather visualization dashboard.

		Args:
			df (pandas.DataFrame): The DataFrame with processed weather data.
			city (str): The name of the city for plot titles.
			save_path (Optional[str]): Path to save the generated image.
			show (bool): Whether to display the plot window.
		"""
		if df is None or df.empty:
			print("No data available to create visualizations.")
			return

		plt.style.use("seaborn-v0_8-darkgrid")
		fig, axes = plt.subplots(
			2,
			2,
			figsize=(20, 14),
			gridspec_kw={"hspace": 0.4, "wspace": 0.3},
		)
		fig.suptitle(
			f"5-Day Weather Forecast for {city.title()}",
			fontsize=24,
			fontweight="bold",
			color="navy",
		)

		# 1. Temperature and Feels Like Trend
		sns.lineplot(
			ax=axes[0, 0],
			x="datetime",
			y="temperature",
			data=df,
			color="crimson",
			marker="o",
			label="Temperature (°C)",
		)
		sns.lineplot(
			ax=axes[0, 0],
			x="datetime",
			y="feels_like",
			data=df,
			color="orange",
			linestyle="--",
			label="Feels Like (°C)",
		)
		axes[0, 0].set_title("Temperature Trends", fontsize=16, fontweight="bold")
		axes[0, 0].set_xlabel("Date and Time", fontsize=12)
		axes[0, 0].set_ylabel("Temperature (°C)", fontsize=12)
		axes[0, 0].tick_params(axis="x", rotation=45)
		axes[0, 0].legend()
		axes[0, 0].grid(True, which="both", linestyle="--", linewidth=0.5)

		# 2. Humidity Trend
		axes[0, 1].fill_between(df["datetime"], df["humidity"], color="deepskyblue", alpha=0.3)
		sns.lineplot(ax=axes[0, 1], x="datetime", y="humidity", data=df, color="dodgerblue", marker=".")
		axes[0, 1].set_title("Humidity Levels", fontsize=16, fontweight="bold")
		axes[0, 1].set_xlabel("Date and Time", fontsize=12)
		axes[0, 1].set_ylabel("Humidity (%)", fontsize=12)
		axes[0, 1].tick_params(axis="x", rotation=45)

		# 3. Wind Speed Forecast
		wind_palette = sns.color_palette("coolwarm", len(df["wind_speed"]))
		x_labels = df["datetime"].dt.strftime("%b-%d %Hh")
		sns.barplot(ax=axes[1, 0], x=x_labels, y=df["wind_speed"], palette=wind_palette)
		axes[1, 0].set_title("Wind Speed Forecast", fontsize=16, fontweight="bold")
		axes[1, 0].set_xlabel("Date and Time", fontsize=12)
		axes[1, 0].set_ylabel("Wind Speed (m/s)", fontsize=12)
		axes[1, 0].tick_params(axis="x", rotation=75)

		# 4. Weather Description Distribution (Pie Chart)
		weather_counts = df["weather_description"].value_counts()
		axes[1, 1].pie(
			weather_counts,
			labels=weather_counts.index,
			autopct="%1.1f%%",
			startangle=140,
			colors=sns.color_palette("Spectral", len(weather_counts)),
		)
		axes[1, 1].set_title("Dominant Weather Conditions", fontsize=16, fontweight="bold")
		axes[1, 1].axis("equal")  # Equal aspect ratio ensures that pie is drawn as a circle.

		plt.tight_layout(rect=[0, 0.03, 1, 0.95])

		# Save and optionally show the plot
		if not save_path:
			safe_city = "".join(c for c in city if c.isalnum() or c in ("-", "_")).rstrip()
			save_path = f"{safe_city}_weather_dashboard.png"
		plt.savefig(save_path, dpi=300)
		if show and os.environ.get("DISPLAY", "") != "":
			plt.show()
		plt.close(fig)


def parse_args(argv):
	parser = argparse.ArgumentParser(
		description="5-day/3-hour weather dashboard using OpenWeatherMap.",
	)
	parser.add_argument(
		"--city",
		"-c",
		required=False,
		help="City name (e.g., London)",
	)
	parser.add_argument(
		"--api-key",
		"-k",
		required=False,
		help="OpenWeatherMap API key. If not provided, reads OPENWEATHER_API_KEY env var.",
	)
	parser.add_argument(
		"--output",
		"-o",
		required=False,
		help="Path to save the generated image.",
	)
	parser.add_argument(
		"--no-show", action="store_true", help="Do not display the plot window (useful on servers)."
	)
	return parser.parse_args(argv)


def main(argv=None):
	"""Main entrypoint."""
	args = parse_args(argv or sys.argv[1:])

	city = args.city or os.getenv("CITY")
	if not city:
		city = input("Enter the city name to get the weather forecast: ").strip()

	api_key = args.api_key or os.getenv("OPENWEATHER_API_KEY")
	if not api_key:
		print("Missing API key. Provide --api-key or set OPENWEATHER_API_KEY.")
		sys.exit(1)

	if not city:
		print("City name cannot be empty.")
		sys.exit(1)

	visualizer = WeatherVisualizer(api_key)
	weather_data = visualizer.fetch_data(city)

	if weather_data:
		df = visualizer.process_data(weather_data)
		visualizer.create_dashboard(df, city, save_path=args.output, show=not args.no_show)
	else:
		sys.exit(2)


if __name__ == "__main__":
	main()