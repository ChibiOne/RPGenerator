# utils/game_objects/world/location.py
import logging
from typing import List, Tuple, Optional, Dict, Any, Union

from ..items import Item
from ..npc import NPC
from .area import Area

class Location:
    """
    Represents a collection of connected areas in the game world.
    Acts as a container for areas and manages their relationships.
    """
    def __init__(
        self,
        name: str,
        description: str = '',
        coordinates: Tuple[float, float] = (0, 0),
        area_names: Optional[List[str]] = None,
        areas: Optional[List[Area]] = None,
        inventory: Optional[List[Item]] = None,
        npcs: Optional[List[NPC]] = None,
        channel_id: Optional[int] = None,
        allows_intercontinental_travel: bool = False,
        **kwargs: Any
    ):
        self.name = name
        self.description = description
        self.coordinates = coordinates
        self.area_names = area_names or []
        self.areas = areas or []
        self.inventory = inventory or []
        self.npcs = npcs or []
        self.channel_id = channel_id
        self.allows_intercontinental_travel = allows_intercontinental_travel

    def to_dict(self) -> Dict[str, Any]:
        """Convert location to dictionary format."""
        return {
            'name': self.name,
            'description': self.description,
            'coordinates': list(self.coordinates),
            'area_names': [area.name for area in self.areas],
            'inventory': [item.name for item in self.inventory],
            'npcs': [npc.name for npc in self.npcs],
            'channel_id': self.channel_id,
            'allows_intercontinental_travel': self.allows_intercontinental_travel
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        item_lookup: Optional[Dict[str, Item]] = None,
        npc_lookup: Optional[Dict[str, NPC]] = None
    ) -> 'Location':
        """
        Create a Location instance from dictionary data.
        
        Args:
            data: The Location data
            item_lookup: Dictionary mapping item names to Item instances
            npc_lookup: Dictionary mapping NPC names to NPC instances
        Returns:
            Location: A new Location instance
        """
        try:
            name = data.get('name', '')
            if not name:
                raise ValueError("Location name is required")

            # Handle inventory conversion
            inventory = []
            if item_lookup and 'inventory' in data:
                inventory = [
                    item_lookup[item_name]
                    for item_name in data['inventory']
                    if item_name in item_lookup
                ]

            # Handle NPC conversion
            npcs = []
            if npc_lookup and 'npcs' in data:
                npcs = [
                    npc_lookup[npc_name]
                    for npc_name in data['npcs']
                    if npc_name in npc_lookup
                ]

            return cls(
                name=name,
                description=data.get('description', ''),
                coordinates=tuple(data.get('coordinates', [0, 0])),
                area_names=data.get('area_names', []),
                inventory=inventory,
                npcs=npcs,
                channel_id=data.get('channel_id'),
                allows_intercontinental_travel=data.get('allows_intercontinental_travel', False)
            )
        except Exception as e:
            logging.error(f"Error creating Location from dict: {e}")
            raise

    def add_area(self, area: Area) -> bool:
        """Add an area to the location."""
        try:
            if area not in self.areas:
                self.areas.append(area)
                if area.name not in self.area_names:
                    self.area_names.append(area.name)
                return True
            return False
        except Exception as e:
            logging.error(f"Error adding area to Location {self.name}: {e}")
            return False

    def remove_area(self, area: Union[Area, str]) -> bool:
        """Remove an area from the location."""
        try:
            if isinstance(area, str):
                area_obj = next((a for a in self.areas if a.name == area), None)
                if area_obj:
                    self.areas.remove(area_obj)
                    if area in self.area_names:
                        self.area_names.remove(area)
                    return True
            elif area in self.areas:
                self.areas.remove(area)
                if area.name in self.area_names:
                    self.area_names.remove(area.name)
                return True
            return False
        except Exception as e:
            logging.error(f"Error removing area from Location {self.name}: {e}")
            return False

    def get_area(self, area_name: str) -> Optional[Area]:
        """Get an area by name."""
        try:
            return next(
                (area for area in self.areas if area.name.lower() == area_name.lower()),
                None
            )
        except Exception as e:
            logging.error(f"Error getting area {area_name} from Location {self.name}: {e}")
            return None

    def get_all_npcs(self) -> List[NPC]:
        """Get all NPCs in this location and its areas."""
        try:
            all_npcs = self.npcs.copy()
            for area in self.areas:
                all_npcs.extend(area.npcs)
            return list(set(all_npcs))  # Remove duplicates
        except Exception as e:
            logging.error(f"Error getting all NPCs from Location {self.name}: {e}")
            return []

    def get_all_items(self) -> List[Item]:
        """Get all items in this location and its areas."""
        try:
            all_items = self.inventory.copy()
            for area in self.areas:
                all_items.extend(area.inventory)
            return list(set(all_items))  # Remove duplicates
        except Exception as e:
            logging.error(f"Error getting all items from Location {self.name}: {e}")
            return []

    def update(self, **kwargs: Any) -> None:
        """Update location attributes."""
        try:
            for key, value in kwargs.items():
                if key == 'inventory' and isinstance(value, list):
                    self.inventory = value
                elif key == 'npcs' and isinstance(value, list):
                    self.npcs = value
                elif key == 'areas' and isinstance(value, list):
                    self.areas = value
                    self.area_names = [area.name for area in value]
                elif hasattr(self, key):
                    setattr(self, key, value)
        except Exception as e:
            logging.error(f"Error updating Location {self.name}: {e}")

    def __repr__(self) -> str:
        return f"<Location: {self.name} ({len(self.areas)} areas)>"