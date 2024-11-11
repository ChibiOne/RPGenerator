# utils/travel_system/conditions.py
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class TravelMode:
    """Available modes of travel"""
    name: str
    speed_multiplier: float
    emoji: str

    @property
    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "speed_multiplier": self.speed_multiplier,
            "emoji": self.emoji
        }

# Define standard travel modes
TRAVEL_MODES = {
    "WALKING": TravelMode("Walking", 1.0, "🚶"),
    "RIDING": TravelMode("Horseback", 2.0, "🐎"),
    "CARRIAGE": TravelMode("Carriage", 1.5, "🛒"),
    "RUNNING": TravelMode("Running", 1.3, "🏃")
}

@dataclass
class WeatherEffect:
    """Weather conditions affecting travel"""
    name: str
    description: str
    speed_modifier: float  # Multiplier for travel time
    danger_level: float   # Affects encounter chance
    emoji: str

# Define available weather conditions
WEATHER_EFFECTS: Dict[str, WeatherEffect] = {
    "clear": WeatherEffect(
        "Clear",
        "Perfect traveling weather",
        1.0,  # Normal speed
        1.0,  # Normal danger
        "☀️"
    ),
    "rain": WeatherEffect(
        "Rain",
        "The rain makes travel slower",
        1.3,  # 30% slower
        1.2,  # 20% more dangerous
        "🌧️"
    ),
    "storm": WeatherEffect(
        "Storm",
        "Thunder and lightning make travel dangerous",
        1.8,  # 80% slower
        1.5,  # 50% more dangerous
        "⛈️"
    ),
    "fog": WeatherEffect(
        "Fog",
        "Limited visibility slows your progress",
        1.4,  # 40% slower
        1.3,  # 30% more dangerous
        "🌫️"
    ),
    "wind": WeatherEffect(
        "Strong Winds",
        "The wind howls around you",
        1.2,  # 20% slower
        1.1,  # 10% more dangerous
        "💨"
    )
}