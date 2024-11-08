# utils/game_objects/world/world.py
import logging
from typing import List, Tuple, Optional, Dict, Any, Union
from collections import defaultdict

from .continent import Continent

class World:
    """
    Represents the top-level game world.
    Contains and manages a collection of continents and provides
    high-level world management functionality.
    """
    def __init__(
        self,
        name: str,
        description: str = '',
        coordinates: Tuple[float, float] = (0, 0),
        continents: Optional[List[Continent]] = None,
        continent_names: Optional[List[str]] = None,
        **kwargs: Any
    ):
        self.name = name
        self.description = description
        self.coordinates = coordinates
        self.continents = continents or []
        self.continent_names = continent_names or []

        # Synchronize continent names if continents were provided
        if continents and not continent_names:
            self.continent_names = [cont.name for cont in continents]

    def to_dict(self) -> Dict[str, Any]:
        """Convert world to dictionary format."""
        return {
            'name': self.name,
            'description': self.description,
            'coordinates': list(self.coordinates),
            'continent_names': self.continent_names
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'World':
        """Create a World instance from dictionary data."""
        try:
            name = data.get('name')
            if not name:
                raise ValueError("World name is required")

            return cls(
                name=name,
                description=data.get('description', ''),
                coordinates=tuple(data.get('coordinates', [0, 0])),
                continent_names=data.get('continent_names', [])
            )
        except Exception as e:
            logging.error(f"Error creating World from dict: {e}")
            raise

    def update(self, **kwargs: Any) -> None:
        """Update world attributes."""
        try:
            for key, value in kwargs.items():
                if key == 'continents' and isinstance(value, list):
                    self.continents = value
                    self.continent_names = [cont.name for cont in value]
                elif hasattr(self, key):
                    setattr(self, key, value)
        except Exception as e:
            logging.error(f"Error updating World {self.name}: {e}")

    def add_continent(self, continent: Continent) -> bool:
        """Add a continent to the world."""
        try:
            if continent not in self.continents:
                self.continents.append(continent)
                if continent.name not in self.continent_names:
                    self.continent_names.append(continent.name)
                return True
            return False
        except Exception as e:
            logging.error(f"Error adding continent to World {self.name}: {e}")
            return False

    def remove_continent(self, continent: Union[Continent, str]) -> bool:
        """Remove a continent from the world."""
        try:
            if isinstance(continent, str):
                continent_obj = next((c for c in self.continents if c.name == continent), None)
                if continent_obj:
                    self.continents.remove(continent_obj)
                    if continent in self.continent_names:
                        self.continent_names.remove(continent)
                    return True
            elif continent in self.continents:
                self.continents.remove(continent)
                if continent.name in self.continent_names:
                    self.continent_names.remove(continent.name)
                return True
            return False
        except Exception as e:
            logging.error(f"Error removing continent from World {self.name}: {e}")
            return False

    def get_continent(self, continent_name: str) -> Optional[Continent]:
        """Get a continent by name."""
        try:
            return next(
                (cont for cont in self.continents if cont.name.lower() == continent_name.lower()),
                None
            )
        except Exception as e:
            logging.error(f"Error getting continent {continent_name} from World {self.name}: {e}")
            return None

    def get_all_regions(self) -> List['Region']:
        """Get all regions across all continents."""
        try:
            all_regions = []
            for continent in self.continents:
                all_regions.extend(continent.regions)
            return list(set(all_regions))  # Remove duplicates
        except Exception as e:
            logging.error(f"Error getting all regions from World {self.name}: {e}")
            return []

    def get_all_locations(self) -> List['Location']:
        """Get all locations across all continents."""
        try:
            all_locations = []
            for continent in self.continents:
                all_locations.extend(continent.get_all_locations())
            return list(set(all_locations))
        except Exception as e:
            logging.error(f"Error getting all locations from World {self.name}: {e}")
            return []

    def get_all_areas(self) -> List['Area']:
        """Get all areas across all continents."""
        try:
            all_areas = []
            for continent in self.continents:
                all_areas.extend(continent.get_all_areas())
            return list(set(all_areas))
        except Exception as e:
            logging.error(f"Error getting all areas from World {self.name}: {e}")
            return []

    def get_travel_network(self) -> Dict[str, List[str]]:
        """Get a mapping of all intercontinental travel connections."""
        try:
            travel_network = defaultdict(list)
            travel_hubs = []
            
            # Collect all travel hubs
            for continent in self.continents:
                continent_hubs = continent.get_travel_hubs()
                travel_hubs.extend(continent_hubs)
                
                # Map connections
                for hub in continent_hubs:
                    for other_hub in travel_hubs:
                        if hub != other_hub:
                            travel_network[hub.name].append(other_hub.name)
                            travel_network[other_hub.name].append(hub.name)
                            
            return dict(travel_network)
        except Exception as e:
            logging.error(f"Error getting travel network for World {self.name}: {e}")
            return {}

    def get_area_by_coordinates(self, coordinates: Tuple[float, float]) -> Optional['Area']:
        """Find the closest area to given coordinates."""
        try:
            all_areas = self.get_all_areas()
            if not all_areas:
                return None
                
            def distance(area: 'Area') -> float:
                x1, y1 = area.coordinates
                x2, y2 = coordinates
                return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            
            return min(all_areas, key=distance)
        except Exception as e:
            logging.error(f"Error finding area by coordinates in World {self.name}: {e}")
            return None

    def get_path_between_areas(self, start_area: 'Area', end_area: 'Area') -> List['Area']:
        """Find a path between two areas using available connections."""
        try:
            # Simple BFS path finding
            visited = set()
            queue = [(start_area, [start_area])]
            
            while queue:
                (current, path) = queue.pop(0)
                
                if current == end_area:
                    return path
                    
                for next_area in current.connected_areas:
                    if next_area not in visited:
                        visited.add(next_area)
                        queue.append((next_area, path + [next_area]))
            
            return []  # No path found
        except Exception as e:
            logging.error(f"Error finding path between areas in World {self.name}: {e}")
            return []

    def __repr__(self) -> str:
        return f"<World: {self.name} ({len(self.continents)} continents)>"