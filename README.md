# Weather-Data-Visualization-Project
import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import sys

class WeatherVisualizer:
    """
    A class to fetch weather data from OpenWeatherMap, process it,
    and create a visually appealing dashboard.
    """
    def __init__(self, api_key):
        """
        Initializes the WeatherVisualizer with the API key.
        
        Args:
            api_key (str): Your OpenWeatherMap API key.
        """
        if api_key == "YOUR_API_KEY" or not api_key:
            print("API Key is missing. Please replace 'YOUR_API_KEY' with your actual key.")
            sys.exit()
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5/forecast"

    def fetch_data(self, city):
        """
        Fetches 5-day/3-hour forecast data for a given city.
        
        Args:
            city (str): The name of the city.
            
        Returns:
            dict: The JSON response from the API, or None if an error occurs.
        """
        params = {'q': city, 'appid': self.api_key, 'units': 'metric'}
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                print(f"Error: City '{city}' not found. Please check the spelling and try again.")
            elif response.status_code == 401:
                print("Error: Invalid API key. Please check your OpenWeatherMap API key.")
            else:
                print(f"An HTTP error occurred: {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"A network error occurred: {e}")
            return None

    def process_data(self, data):
        """
        Processes the raw JSON data into a clean pandas DataFrame.
        
        Args:
            data (dict): The JSON data from the API.
            
        Returns:
            pandas.DataFrame: A DataFrame with structured weather information.
        """
        if not data:
            return None

        forecast_list = [
            {
                'datetime': datetime.fromtimestamp(item['dt']),
                'temperature': item['main']['temp'],
                'feels_like': item['main']['feels_like'],
                'humidity': item['main']['humidity'],
                'wind_speed': item['wind']['speed'],
                'weather_description': item['weather'][0]['description'].title()
            }
            for item in data['list']
        ]
        return pd.DataFrame(forecast_list)

    def create_dashboard(self, df, city):
        """
        Creates a beautiful and informative weather visualization dashboard.
        
        Args:
            df (pandas.DataFrame): The DataFrame with processed weather data.
            city (str): The name of the city for plot titles.
        """
        if df is None or df.empty:
            print("No data available to create visualizations.")
            return

        plt.style.use('seaborn-v0_8-darkgrid')
        fig, axes = plt.subplots(2, 2, figsize=(20, 14), gridspec_kw={'hspace': 0.4, 'wspace': 0.3})
        fig.suptitle(f'5-Day Weather Forecast for {city.title()}', fontsize=24, fontweight='bold', color='navy')

        # 1. Temperature and Feels Like Trend
        sns.lineplot(ax=axes[0, 0], x='datetime', y='temperature', data=df, color='crimson', marker='o', label='Temperature (°C)')
        sns.lineplot(ax=axes[0, 0], x='datetime', y='feels_like', data=df, color='orange', linestyle='--', label='Feels Like (°C)')
        axes[0, 0].set_title('Temperature Trends', fontsize=16, fontweight='bold')
        axes[0, 0].set_xlabel('Date and Time', fontsize=12)
        axes[0, 0].set_ylabel('Temperature (°C)', fontsize=12)
        axes[0, 0].tick_params(axis='x', rotation=45)
        axes[0, 0].legend()
        axes[0, 0].grid(True, which='both', linestyle='--', linewidth=0.5)

        # 2. Humidity Trend
        axes[0, 1].fill_between(df['datetime'], df['humidity'], color="deepskyblue", alpha=0.3)
        sns.lineplot(ax=axes[0, 1], x='datetime', y='humidity', data=df, color="dodgerblue", marker='.')
        axes[0, 1].set_title('Humidity Levels', fontsize=16, fontweight='bold')
        axes[0, 1].set_xlabel('Date and Time', fontsize=12)
        axes[0, 1].set_ylabel('Humidity (%)', fontsize=12)
        axes[0, 1].tick_params(axis='x', rotation=45)

        # 3. Wind Speed Forecast
        wind_palette = sns.color_palette("coolwarm", len(df['wind_speed']))
        sns.barplot(ax=axes[1, 0], x=df['datetime'].dt.strftime('%b-%d %Hh'), y='wind_speed', data=df, palette=wind_palette)
        axes[1, 0].set_title('Wind Speed Forecast', fontsize=16, fontweight='bold')
        axes[1, 0].set_xlabel('Date and Time', fontsize=12)
        axes[1, 0].set_ylabel('Wind Speed (m/s)', fontsize=12)
        axes[1, 0].tick_params(axis='x', rotation=75)

        # 4. Weather Description Distribution (Pie Chart)
        weather_counts = df['weather_description'].value_counts()
        axes[1, 1].pie(weather_counts, labels=weather_counts.index, autopct='%1.1f%%', startangle=140,
                        colors=sns.color_palette("Spectral", len(weather_counts)))
        axes[1, 1].set_title('Dominant Weather Conditions', fontsize=16, fontweight='bold')
        axes[1, 1].axis('equal') # Equal aspect ratio ensures that pie is drawn as a circle.

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        # Save and show the plot
        plt.savefig(f'{city}_weather_dashboard.png', dpi=300)
        plt.show()

def main():
    """
    Main function to run the application.
    """
    # !!! IMPORTANT: Replace "YOUR_API_KEY" with your actual OpenWeatherMap API key
    api_key = "a2a9749ebb981c5126bd001ce6af3c88"  
    
    city = input("Enter the city name to get the weather forecast: ").strip()
    
    if not city:
        print("City name cannot be empty.")
        return

    visualizer = WeatherVisualizer(api_key)
    weather_data = visualizer.fetch_data(city)
    
    if weather_data:
        df = visualizer.process_data(weather_data)
        visualizer.create_dashboard(df, city)

if __name__ == "__main__":
    main()
