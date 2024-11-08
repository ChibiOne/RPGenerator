# utils/travel_conditions.py
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class TravelMode:
    """Available modes of travel"""
    WALKING = {"name": "Walking", "speed_multiplier": 1.0, "emoji": "🚶"}
    RIDING = {"name": "Horseback", "speed_multiplier": 2.0, "emoji": "🐎"}
    CARRIAGE = {"name": "Carriage", "speed_multiplier": 1.5, "emoji": "🛒"}
    RUNNING = {"name": "Running", "speed_multiplier": 1.3, "emoji": "🏃"}

@dataclass
class WeatherEffect:
    """Weather conditions affecting travel"""
    name: str
    description: str
    speed_modifier: float  # Multiplier for travel time
    danger_level: float   # Affects encounter chance

# Define available weather conditions
WEATHER_EFFECTS: Dict[str, WeatherEffect] = {
    "clear": WeatherEffect(
        "Clear",
        "Perfect traveling weather",
        1.0,  # Normal speed
        1.0   # Normal danger
    ),
    "rain": WeatherEffect(
        "Rain",
        "The rain makes travel slower",
        1.3,  # 30% slower
        1.2   # 20% more dangerous
    ),
    "storm": WeatherEffect(
        "Storm",
        "Thunder and lightning make travel dangerous",
        1.8,  # 80% slower
        1.5   # 50% more dangerous
    ),
    "fog": WeatherEffect(
        "Fog",
        "Limited visibility slows your progress",
        1.4,  # 40% slower
        1.3   # 30% more dangerous
    ),
    "wind": WeatherEffect(
        "Strong Winds",
        "The wind howls around you",
        1.2,  # 20% slower
        1.1   # 10% more dangerous
    )
}