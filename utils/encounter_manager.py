# utils/encounter_manager.py
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import random
import logging
from .redis_manager import ShardAwareRedisDB

@dataclass
class Encounter:
    """Represents a possible encounter during travel"""
    id: str
    name: str
    type: str  # 'combat' or 'event'
    description: str
    danger_level: int
    required_party_level: int
    rewards: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Encounter':
        return cls(
            id=data['id'],
            name=data['name'],
            type=data['type'],
            description=data['description'],
            danger_level=data['danger_level'],
            required_party_level=data['required_party_level'],
            rewards=data.get('rewards', {})
        )

class EncounterManager:
    def __init__(self, redis_db: ShardAwareRedisDB):
        self.redis_db = redis_db
        self._encounters_cache = None
        self._cache_time = 0

    async def get_encounters(self) -> List[Encounter]:
        """Get all possible encounters from Redis or load from cache"""
        try:
            if not self._encounters_cache:
                encounters_data = await self.redis_db.get('encounters')
                if encounters_data:
                    self._encounters_cache = [
                        Encounter.from_dict(enc) for enc in encounters_data
                    ]
            return self._encounters_cache or []
        except Exception as e:
            logging.error(f"Error loading encounters: {e}")
            return []

    def calculate_danger_chance(self, from_area: 'Area', to_area: 'Area', 
                              weather: 'WeatherEffect') -> float:
        """
        Calculate the chance of an encounter based on area danger levels and weather
        Args:
            from_area: Starting area
            to_area: Destination area
            weather: Current weather conditions
        Returns:
            float: Chance of encounter (0.0 to 0.9)
        """
        try:
            # Base chance is average of the two areas' danger levels
            base_chance = (from_area.danger_level + to_area.danger_level) / 20.0
            
            # Add modifier based on danger level difference
            level_difference = abs(from_area.danger_level - to_area.danger_level)
            difference_modifier = level_difference * 0.05
            
            # Combine base chance and modifiers
            total_chance = base_chance + difference_modifier
            
            # Apply weather modifier
            total_chance *= weather.danger_level
            
            # Ensure the chance stays within reasonable bounds
            return min(max(total_chance, 0.0), 0.9)
            
        except Exception as e:
            logging.error(f"Error calculating danger chance: {e}")
            return 0.0

    async def generate_encounter(self, party: 'TravelParty', weather: 'WeatherEffect',
                               from_area: 'Area', to_area: 'Area') -> Optional[Encounter]:
        """
        Generate a random encounter based on party level, conditions, and area danger
        Args:
            party: The traveling party
            weather: Current weather conditions
            from_area: Starting area
            to_area: Destination area
        Returns:
            Optional[Encounter]: Generated encounter or None
        """
        try:
            # Calculate chance based on area danger levels
            encounter_chance = self.calculate_danger_chance(from_area, to_area, weather)
            
            # If both areas are safe (level 0), no encounters
            if from_area.danger_level == 0 and to_area.danger_level == 0:
                return None
                
            if random.random() > encounter_chance:
                return None

            # Get the maximum danger level between the two areas
            max_danger = max(from_area.danger_level, to_area.danger_level)
            
            # Get all possible encounters
            all_encounters = await self.get_encounters()
            
            # Filter encounters based on party level and area danger
            possible_encounters = [
                enc for enc in all_encounters
                if enc.required_party_level <= party.get_average_level()
                and enc.danger_level <= max_danger
            ]
            
            if not possible_encounters:
                return None

            # Weight encounter selection based on weather and area danger
            weighted_encounters = []
            for enc in possible_encounters:
                # More dangerous encounters in more dangerous areas
                danger_weight = max(1, int(max_danger / 2))
                
                if enc.type == "combat":
                    if weather.danger_level > 1.2:
                        # More combat in dangerous weather
                        weighted_encounters.extend([enc] * (danger_weight * 2))
                    else:
                        weighted_encounters.extend([enc] * danger_weight)
                elif enc.type == "event":
                    if weather.danger_level < 1.2:
                        # More events in good weather
                        weighted_encounters.extend([enc] * 2)
                    else:
                        weighted_encounters.append(enc)
                else:
                    weighted_encounters.append(enc)

            return random.choice(weighted_encounters) if weighted_encounters else None

        except Exception as e:
            logging.error(f"Error generating encounter: {e}")
            return None

    async def cache_encounter_result(self, party_id: str, encounter: Encounter, 
                                   result: Dict[str, Any]):
        """Cache the result of an encounter for later reference"""
        try:
            key = f"encounter_result:{party_id}:{encounter.id}"
            await self.redis_db.set(key, result, expire=3600)  # Cache for 1 hour
        except Exception as e:
            logging.error(f"Error caching encounter result: {e}")

    async def get_recent_encounters(self, party_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent encounters for a party"""
        try:
            pattern = f"encounter_result:{party_id}:*"
            results = []
            async for key in self.redis_db.scan_iter(pattern):
                result = await self.redis_db.get(key)
                if result:
                    results.append(result)
            return sorted(results, key=lambda x: x.get('timestamp', 0), reverse=True)[:limit]
        except Exception as e:
            logging.error(f"Error getting recent encounters: {e}")
            return []