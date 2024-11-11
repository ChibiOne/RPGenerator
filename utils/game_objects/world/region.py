# utils/game_objects/world/region.py
import logging
from typing import List, Tuple, Optional, Dict, Any, Union

from .location import Location

class Region:
    """
    Represents a geographical region in the game world.
    Contains and manages a collection of locations.
    """
    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        coordinates: Tuple[float, float] = (0, 0),
        locations: Optional[List[Location]] = None,
        location_names: Optional[List[str]] = None,
        **kwargs: Any
    ):
        self.name = name
        self.description = description or ''
        self.coordinates = coordinates
        self.locations = locations or []
        self.location_names = location_names or []
        
        # Synchronize location names if locations were provided
        if locations and not location_names:
            self.location_names = [loc.name for loc in locations]

    def to_dict(self) -> Dict[str, Any]:
        """Convert region to dictionary format."""
        return {
            'name': self.name,
            'description': self.description,
            'coordinates': list(self.coordinates),
            'location_names': self.location_names
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Region':
        """Create a Region instance from dictionary data."""
        try:
            logging.info(f"Parsing Region data: {data}")
            name = data.get('name')
            if not name:
                raise ValueError("Region name is required")

            return cls(
                name=name,
                description=data.get('description', ''),
                coordinates=tuple(data.get('coordinates', [0, 0])),
                location_names=data.get('location_names', [])
            )
        except Exception as e:
            logging.error(f"Error creating Region from dict: {e}")
            raise

    def update(self, **kwargs: Any) -> None:
        """Update region attributes."""
        try:
            for key, value in kwargs.items():
                if key == 'locations' and isinstance(value, list):
                    self.locations = value
                    self.location_names = [loc.name for loc in value]
                elif hasattr(self, key):
                    setattr(self, key, value)
        except Exception as e:
            logging.error(f"Error updating Region {self.name}: {e}")

    def add_location(self, location: Location) -> bool:
        """Add a location to the region."""
        try:
            if location not in self.locations:
                self.locations.append(location)
                if location.name not in self.location_names:
                    self.location_names.append(location.name)
                return True
            return False
        except Exception as e:
            logging.error(f"Error adding location to Region {self.name}: {e}")
            return False

    def remove_location(self, location: Union[Location, str]) -> bool:
        """Remove a location from the region."""
        try:
            if isinstance(location, str):
                location_obj = next((loc for loc in self.locations if loc.name == location), None)
                if location_obj:
                    self.locations.remove(location_obj)
                    if location in self.location_names:
                        self.location_names.remove(location)
                    return True
            elif location in self.locations:
                self.locations.remove(location)
                if location.name in self.location_names:
                    self.location_names.remove(location.name)
                return True
            return False
        except Exception as e:
            logging.error(f"Error removing location from Region {self.name}: {e}")
            return False

    def get_location(self, location_name: str) -> Optional[Location]:
        """Get a location by name."""
        try:
            return next(
                (loc for loc in self.locations if loc.name.lower() == location_name.lower()),
                None
            )
        except Exception as e:
            logging.error(f"Error getting location {location_name} from Region {self.name}: {e}")
            return None

    def get_all_areas(self) -> List['Area']:
        """Get all areas across all locations in this region."""
        try:
            all_areas = []
            for location in self.locations:
                all_areas.extend(location.areas)
            return list(set(all_areas))  # Remove duplicates
        except Exception as e:
            logging.error(f"Error getting all areas from Region {self.name}: {e}")
            return []

    def get_all_npcs(self) -> List['NPC']:
        """Get all NPCs across all locations in this region."""
        try:
            all_npcs = []
            for location in self.locations:
                all_npcs.extend(location.get_all_npcs())
            return list(set(all_npcs))  # Remove duplicates
        except Exception as e:
            logging.error(f"Error getting all NPCs from Region {self.name}: {e}")
            return []

    def calculate_center(self) -> Tuple[float, float]:
        """Calculate the geometric center of all locations in this region."""
        try:
            if not self.locations:
                return self.coordinates
            
            x_coords = [loc.coordinates[0] for loc in self.locations]
            y_coords = [loc.coordinates[1] for loc in self.locations]
            
            center_x = sum(x_coords) / len(x_coords)
            center_y = sum(y_coords) / len(y_coords)
            
            return (center_x, center_y)
        except Exception as e:
            logging.error(f"Error calculating center for Region {self.name}: {e}")
            return self.coordinates

    def get_closest_location(self, coordinates: Tuple[float, float]) -> Optional[Location]:
        """Find the location closest to given coordinates."""
        try:
            if not self.locations:
                return None
                
            def distance(loc: Location) -> float:
                x1, y1 = loc.coordinates
                x2, y2 = coordinates
                return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            
            return min(self.locations, key=distance)
        except Exception as e:
            logging.error(f"Error finding closest location in Region {self.name}: {e}")
            return None

    def __repr__(self) -> str:
        return f"<Region: {self.name} ({len(self.locations)} locations)>"