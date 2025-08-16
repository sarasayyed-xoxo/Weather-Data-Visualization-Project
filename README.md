# Weather-Data-Visualization-Project

A professional CLI tool to fetch a 5-day/3-hour forecast from OpenWeatherMap and generate a visual dashboard.

## Quickstart

1) Install dependencies:

```bash
pip install -r requirements.txt
```

2) Provide your API key (recommended via environment):

```bash
export OPENWEATHER_API_KEY=YOUR_API_KEY_HERE
```

Optionally, create a `.env` file with:

```bash
OPENWEATHER_API_KEY=YOUR_API_KEY_HERE
```

3) Run the tool:

```bash
python weather_visualizer.py --city "London" --units metric
```

- Add `--output london.png` to change the saved image path
- Add `--no-show` for headless environments
- Add `--verbose` for debug logging

## Examples

```bash
python weather_visualizer.py -c "New York" -u imperial -o nyc_dashboard.png
```

## Notes
- Uses HTTPS, robust retry logic, and structured logging
- Supports languages via `--lang` (e.g., `-l en`)
- Units: `metric`, `imperial`, or `standard`