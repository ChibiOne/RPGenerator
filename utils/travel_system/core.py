# utils/travel_system/core.py
import logging
import math
from typing import Tuple, Optional, Dict, Any

from .conditions import TravelMode, WeatherEffect

class TravelSystem:
    """Core travel system handling movement and calculations."""
    
    @staticmethod
    def calculate_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """Calculate distance between two coordinate points."""
        try:
            x1, y1 = coord1
            x2, y2 = coord2
            return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        except Exception as e:
            logging.error(f"Error calculating distance: {e}")
            return 0.0
    
    @staticmethod
    def calculate_travel_time(
        distance: float,
        travel_mode: Optional[TravelMode] = None,
        weather: Optional[WeatherEffect] = None
    ) -> float:
        """Calculate travel time based on distance and conditions."""
        try:
            base_time = distance * 60  # Base time in seconds
            
            # Apply travel mode modifier
            if travel_mode:
                base_time /= travel_mode.speed_modifier
            
            # Apply weather modifier
            if weather:
                base_time *= weather.speed_modifier
            
            return max(60, base_time)  # Minimum 1 minute travel time
            
        except Exception as e:
            logging.error(f"Error calculating travel time: {e}")
            return 60.0  # Default to 1 minute on error