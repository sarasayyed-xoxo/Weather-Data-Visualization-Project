import argparse
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
	from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
	load_dotenv = None  # type: ignore


API_URL = "https://api.openweathermap.org/data/2.5/forecast"
DEFAULT_UNITS = "metric"
SUPPORTED_UNITS = {"metric", "imperial", "standard"}
DEFAULT_TIMEOUT_SECONDS = 15


@dataclass
class WeatherApiConfig:
	api_key: str
	units: str = DEFAULT_UNITS
	lang: Optional[str] = None
	timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


class WeatherVisualizer:
	"""
	Fetch 5-day/3-hour forecast data from OpenWeatherMap, process it, and build a dashboard.
	"""

	def __init__(self, config: WeatherApiConfig, session: Optional["requests.Session"] = None) -> None:
		# Import here to avoid hard dependency at module import time
		import requests  # type: ignore

		if not config.api_key:
			raise ValueError("OpenWeatherMap API key is required. Provide via --api-key or OPENWEATHER_API_KEY.")
		if config.units not in SUPPORTED_UNITS:
			raise ValueError(f"Unsupported units '{config.units}'. Use one of: {', '.join(sorted(SUPPORTED_UNITS))}.")

		self.config = config
		self.session = session or self._build_session_with_retries()

	@staticmethod
	def _build_session_with_retries() -> "requests.Session":
		# Import here to avoid hard dependency at module import time
		import requests  # type: ignore
		# Configure a Session with HTTPAdapter retries and backoff
		session = requests.Session()
		try:
			from requests.adapters import HTTPAdapter  # type: ignore
			from urllib3.util.retry import Retry  # type: ignore

			retry = Retry(
				total=5,
				read=5,
				connect=5,
				backoff_factor=0.5,
				status_forcelist=(429, 500, 502, 503, 504),
				allowed_methods=("HEAD", "GET", "OPTIONS"),
			)
			adapter = HTTPAdapter(max_retries=retry)
			session.mount("http://", adapter)
			session.mount("https://", adapter)
		except Exception:
			# If urllib3 Retry isn't available, proceed without it
			logging.debug("Retry adapter not available; using default Session without retries.")
		return session

	def fetch_data(self, city: str) -> Optional[Dict[str, Any]]:
		"""
		Fetch 5-day/3-hour forecast data for the given city.
		Returns the JSON response as a dict or None if an error occurs.
		"""
		# Import here to avoid hard dependency at module import time
		import requests  # type: ignore

		params: Dict[str, Any] = {
			"q": city,
			"appid": self.config.api_key,
			"units": self.config.units,
		}
		if self.config.lang:
			params["lang"] = self.config.lang

		try:
			logging.info("Requesting forecast for '%s'...", city)
			response = self.session.get(API_URL, params=params, timeout=self.config.timeout_seconds)
			response.raise_for_status()
			return response.json()
		except requests.exceptions.HTTPError as http_error:
			status = getattr(http_error.response, "status_code", None)
			if status == 404:
				logging.error("City '%s' not found (404). Check the spelling and try again.", city)
			elif status == 401:
				logging.error("Invalid API key (401). Verify your OpenWeatherMap API key.")
			else:
				logging.error("HTTP error while fetching data: %s", http_error)
			return None
		except requests.exceptions.RequestException as req_error:
			logging.error("Network error while fetching data: %s", req_error)
			return None

	def process_data(self, data: Dict[str, Any]):
		"""
		Transform raw JSON into a tidy pandas DataFrame.
		"""
		# Lazy import to allow --help without third-party deps
		import pandas as pd  # type: ignore

		if not data or "list" not in data:
			logging.error("Unexpected API response format; missing 'list' field.")
			return None

		records: List[Dict[str, Any]] = []
		for item in data.get("list", []):
			try:
				record = {
					"datetime": pd.to_datetime(item["dt"], unit="s"),
					"temperature": float(item["main"]["temp"]),
					"feels_like": float(item["main"]["feels_like"]),
					"humidity": float(item["main"]["humidity"]),
					"wind_speed": float(item.get("wind", {}).get("speed", float("nan"))),
					"weather_description": str(item.get("weather", [{}])[0].get("description", "")).title(),
				}
				records.append(record)
			except Exception as parse_error:
				logging.debug("Skipping malformed item due to parse error: %s", parse_error)

		if not records:
			logging.error("No valid forecast records were parsed from the API response.")
			return None

		df = pd.DataFrame.from_records(records)
		df.sort_values("datetime", inplace=True)
		df["datetime_label"] = df["datetime"].dt.strftime("%b-%d %Hh")
		return df

	def create_dashboard(
		self,
		df,
		city: str,
		*,
		show: bool = True,
		output_path: Optional[str] = None,
	) -> Optional[str]:
		"""
		Create and optionally save/show the visualization dashboard.
		Returns the saved image path if saved, else None.
		"""
		# Lazy imports to allow --help without third-party deps
		import matplotlib.pyplot as plt  # type: ignore
		import seaborn as sns  # type: ignore

		if df is None or getattr(df, "empty", False):
			logging.warning("No data available to create visualizations.")
			return None

		# Styling
		sns.set_theme(style="darkgrid")
		fig, axes = plt.subplots(2, 2, figsize=(20, 14), gridspec_kw={"hspace": 0.4, "wspace": 0.3})
		fig.suptitle(f"5-Day Weather Forecast for {city.title()}", fontsize=24, fontweight="bold", color="navy")

		# 1. Temperature and Feels Like Trend
		sns.lineplot(ax=axes[0, 0], data=df, x="datetime", y="temperature", color="crimson", marker="o", label="Temperature (°C)")
		sns.lineplot(ax=axes[0, 0], data=df, x="datetime", y="feels_like", color="orange", linestyle="--", label="Feels Like (°C)")
		axes[0, 0].set_title("Temperature Trends", fontsize=16, fontweight="bold")
		axes[0, 0].set_xlabel("Date and Time", fontsize=12)
		axes[0, 0].set_ylabel("Temperature (°C)", fontsize=12)
		axes[0, 0].tick_params(axis="x", rotation=45)
		axes[0, 0].legend()
		axes[0, 0].grid(True, which="both", linestyle="--", linewidth=0.5)

		# 2. Humidity Trend
		axes[0, 1].fill_between(df["datetime"].values, df["humidity"].values, color="deepskyblue", alpha=0.3)
		sns.lineplot(ax=axes[0, 1], data=df, x="datetime", y="humidity", color="dodgerblue", marker=".")
		axes[0, 1].set_title("Humidity Levels", fontsize=16, fontweight="bold")
		axes[0, 1].set_xlabel("Date and Time", fontsize=12)
		axes[0, 1].set_ylabel("Humidity (%)", fontsize=12)
		axes[0, 1].tick_params(axis="x", rotation=45)

		# 3. Wind Speed Forecast (use Matplotlib bar for exact values order)
		wind_palette = sns.color_palette("coolwarm", len(df))
		axes[1, 0].bar(df["datetime_label"], df["wind_speed"], color=wind_palette)
		axes[1, 0].set_title("Wind Speed Forecast", fontsize=16, fontweight="bold")
		axes[1, 0].set_xlabel("Date and Time", fontsize=12)
		axes[1, 0].set_ylabel("Wind Speed (m/s)", fontsize=12)
		axes[1, 0].tick_params(axis="x", rotation=75)

		# 4. Weather Description Distribution (Pie Chart)
		weather_counts = df["weather_description"].value_counts()
		axes[1, 1].pie(
			weather_counts.values,
			labels=weather_counts.index,
			autopct="%1.1f%%",
			startangle=140,
			colors=sns.color_palette("Spectral", len(weather_counts)),
		)
		axes[1, 1].set_title("Dominant Weather Conditions", fontsize=16, fontweight="bold")
		axes[1, 1].axis("equal")  # Equal aspect ratio ensures that pie is a circle.

		plt.tight_layout(rect=[0, 0.03, 1, 0.95])

		# Save and optionally show the plot
		saved_path: Optional[str] = None
		if output_path is None:
			output_path = f"{self._slugify(city)}_weather_dashboard.png"
		try:
			plt.savefig(output_path, dpi=300, bbox_inches="tight")
			saved_path = output_path
			logging.info("Dashboard saved to %s", output_path)
		except Exception as save_error:
			logging.error("Failed to save dashboard: %s", save_error)
		finally:
			if show:
				try:
					plt.show()
				except Exception:
					# Non-interactive environment might not support show()
					logging.debug("Matplotlib show() not supported in this environment.")
			plt.close(fig)

		return saved_path

	@staticmethod
	def _slugify(value: str) -> str:
		return "".join(c.lower() if c.isalnum() else "_" for c in value).strip("_")


def configure_logging(verbose: bool = False) -> None:
	level = logging.DEBUG if verbose else logging.INFO
	logging.basicConfig(
		level=level,
		format="%(asctime)s | %(levelname)s | %(message)s",
		datefmt="%Y-%m-%d %H:%M:%S",
	)


def resolve_api_key(cli_key: Optional[str]) -> str:
	# 1) CLI overrides
	if cli_key:
		return cli_key
	# 2) Load from .env if available, then environment
	if load_dotenv is not None:
		try:
			load_dotenv()
		except Exception:
			pass
	return os.environ.get("OPENWEATHER_API_KEY", "")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Weather Forecast Dashboard using OpenWeatherMap")
	parser.add_argument("--city", "-c", type=str, required=False, help="City name (e.g., London)")
	parser.add_argument("--api-key", "-k", dest="api_key", type=str, help="OpenWeatherMap API key. Overrides env var OPENWEATHER_API_KEY")
	parser.add_argument("--units", "-u", type=str, default=DEFAULT_UNITS, choices=sorted(SUPPORTED_UNITS), help="Units for temperature and wind speed")
	parser.add_argument("--lang", "-l", type=str, default=None, help="Language for weather description (e.g., en, fr, es)")
	parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP request timeout in seconds")
	parser.add_argument("--no-show", action="store_true", help="Do not display the figure window")
	parser.add_argument("--output", "-o", type=str, default=None, help="Output image path for the dashboard PNG")
	parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose (debug) logging")
	return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
	args = parse_args(argv)
	configure_logging(verbose=args.verbose)

	city = args.city
	if not city:
		try:
			city = input("Enter the city name to get the weather forecast: ").strip()
		except EOFError:
			city = ""

	if not city:
		logging.error("City name cannot be empty.")
		return 2

	api_key = resolve_api_key(args.api_key)
	if not api_key:
		logging.error("API key is missing. Provide --api-key or set OPENWEATHER_API_KEY in your environment.")
		return 2

	config = WeatherApiConfig(api_key=api_key, units=args.units, lang=args.lang, timeout_seconds=args.timeout)
	visualizer = WeatherVisualizer(config=config)

	data = visualizer.fetch_data(city)
	if not data:
		return 1

	df = visualizer.process_data(data)
	if df is None or df.empty:
		logging.error("No data available after processing.")
		return 1

	visualizer.create_dashboard(df, city, show=not args.no_show, output_path=args.output)
	return 0


if __name__ == "__main__":
	sys.exit(main())