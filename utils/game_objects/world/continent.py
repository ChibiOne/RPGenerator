# utils/game_objects/world/continent.py
import logging
from typing import List, Tuple, Optional, Dict, Any, Union

from .region import Region

class Continent:
    """
    Represents a major landmass in the game world.
    Contains and manages a collection of regions.
    """
    def __init__(
        self,
        name: str,
        description: str = '',
        coordinates: Tuple[float, float] = (0, 0),
        regions: Optional[List[Region]] = None,
        region_names: Optional[List[str]] = None,
        **kwargs: Any
    ):
        self.name = name
        self.description = description
        self.coordinates = coordinates
        self.regions = regions or []
        self.region_names = region_names or []

        # Synchronize region names if regions were provided
        if regions and not region_names:
            self.region_names = [region.name for region in regions]

    def to_dict(self) -> Dict[str, Any]:
        """Convert continent to dictionary format."""
        return {
            'name': self.name,
            'description': self.description,
            'coordinates': list(self.coordinates),
            'region_names': self.region_names
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Continent':
        """Create a Continent instance from dictionary data."""
        try:
            name = data.get('name')
            if not name:
                raise ValueError("Continent name is required")

            return cls(
                name=name,
                description=data.get('description', ''),
                coordinates=tuple(data.get('coordinates', [0, 0])),
                region_names=data.get('region_names', [])
            )
        except Exception as e:
            logging.error(f"Error creating Continent from dict: {e}")
            raise

    def update(self, **kwargs: Any) -> None:
        """Update continent attributes."""
        try:
            for key, value in kwargs.items():
                if key == 'regions' and isinstance(value, list):
                    self.regions = value
                    self.region_names = [region.name for region in value]
                elif hasattr(self, key):
                    setattr(self, key, value)
        except Exception as e:
            logging.error(f"Error updating Continent {self.name}: {e}")

    def add_region(self, region: Region) -> bool:
        """Add a region to the continent."""
        try:
            if region not in self.regions:
                self.regions.append(region)
                if region.name not in self.region_names:
                    self.region_names.append(region.name)
                return True
            return False
        except Exception as e:
            logging.error(f"Error adding region to Continent {self.name}: {e}")
            return False

    def remove_region(self, region: Union[Region, str]) -> bool:
        """Remove a region from the continent."""
        try:
            if isinstance(region, str):
                region_obj = next((r for r in self.regions if r.name == region), None)
                if region_obj:
                    self.regions.remove(region_obj)
                    if region in self.region_names:
                        self.region_names.remove(region)
                    return True
            elif region in self.regions:
                self.regions.remove(region)
                if region.name in self.region_names:
                    self.region_names.remove(region.name)
                return True
            return False
        except Exception as e:
            logging.error(f"Error removing region from Continent {self.name}: {e}")
            return False

    def get_region(self, region_name: str) -> Optional[Region]:
        """Get a region by name."""
        try:
            return next(
                (region for region in self.regions if region.name.lower() == region_name.lower()),
                None
            )
        except Exception as e:
            logging.error(f"Error getting region {region_name} from Continent {self.name}: {e}")
            return None

    def get_all_locations(self) -> List['Location']:
        """Get all locations across all regions in this continent."""
        try:
            all_locations = []
            for region in self.regions:
                all_locations.extend(region.locations)
            return list(set(all_locations))  # Remove duplicates
        except Exception as e:
            logging.error(f"Error getting all locations from Continent {self.name}: {e}")
            return []

    def get_all_areas(self) -> List['Area']:
        """Get all areas across all regions in this continent."""
        try:
            all_areas = []
            for region in self.regions:
                all_areas.extend(region.get_all_areas())
            return list(set(all_areas))  # Remove duplicates
        except Exception as e:
            logging.error(f"Error getting all areas from Continent {self.name}: {e}")
            return []

    def calculate_center(self) -> Tuple[float, float]:
        """Calculate the geometric center of all regions in this continent."""
        try:
            if not self.regions:
                return self.coordinates
            
            x_coords = [region.coordinates[0] for region in self.regions]
            y_coords = [region.coordinates[1] for region in self.regions]
            
            center_x = sum(x_coords) / len(x_coords)
            center_y = sum(y_coords) / len(y_coords)
            
            return (center_x, center_y)
        except Exception as e:
            logging.error(f"Error calculating center for Continent {self.name}: {e}")
            return self.coordinates

    def get_closest_region(self, coordinates: Tuple[float, float]) -> Optional[Region]:
        """Find the region closest to given coordinates."""
        try:
            if not self.regions:
                return None
                
            def distance(reg: Region) -> float:
                x1, y1 = reg.coordinates
                x2, y2 = coordinates
                return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            
            return min(self.regions, key=distance)
        except Exception as e:
            logging.error(f"Error finding closest region in Continent {self.name}: {e}")
            return None

    def get_travel_hubs(self) -> List['Area']:
        """Get all areas that allow intercontinental travel."""
        try:
            return [
                area for area in self.get_all_areas()
                if area.allows_intercontinental_travel
            ]
        except Exception as e:
            logging.error(f"Error getting travel hubs from Continent {self.name}: {e}")
            return []

    def __repr__(self) -> str:
        return f"<Continent: {self.name} ({len(self.regions)} regions)>"