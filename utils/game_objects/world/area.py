# utils/game_objects/world/area.py
import logging
from typing import List, Tuple, Optional, Dict, Any, Union

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..items import Item
    from ..npc import NPC

class Area:
    """
    Represents a specific area in the game world.
    Base unit of player interaction and movement.
    """
    def __init__(
        self,
        name: str,
        description: str = '',
        coordinates: Tuple[float, float] = (0, 0),
        connected_area_names: Optional[List[str]] = None,
        connected_areas: Optional[List['Area']] = None,
        inventory: Optional[List[Any]] = None,  # Runtime type: List[Item]
        npc_names: Optional[List[str]] = None,
        npcs: Optional[List[Any]] = None,  # Runtime type: List[NPC]
        channel_id: Optional[int] = None,
        allows_intercontinental_travel: bool = False,
        danger_level: int = 0,
        **kwargs: Any
    ):
        self.name = name
        self.description = description
        self.coordinates = coordinates
        self.connected_area_names = connected_area_names or []
        self.connected_areas = connected_areas or []
        self.inventory = inventory or []
        self.npc_names = npc_names or []
        self.npcs = npcs or []
        self.channel_id = channel_id
        self.allows_intercontinental_travel = allows_intercontinental_travel
        self.danger_level = max(0, min(danger_level, 10))  # Clamp between 0 and 10

    def to_dict(self) -> Dict[str, Any]:
        """Convert area to dictionary format."""
        return {
            'name': self.name,
            'description': self.description,
            'coordinates': list(self.coordinates),
            'connected_areas': [area.name for area in self.connected_areas],
            'inventory': [item.name for item in self.inventory],
            'npcs': [npc.name for npc in self.npcs],
            'channel_id': self.channel_id,
            'allows_intercontinental_travel': self.allows_intercontinental_travel,
            'danger_level': self.danger_level
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], item_lookup: Optional[Dict[str, Any]] = None) -> 'Area':  # Runtime type: Dict[str, Item]
        """Create area from dictionary data."""
        try:
            name = data.get('name', '')
            if not name:
                raise ValueError("Area name is required")

            # Handle inventory conversion if lookup is provided
            inventory = []
            if item_lookup and 'inventory' in data:
                inventory = [
                    item_lookup[item_name]
                    for item_name in data['inventory']
                    if item_name in item_lookup
                ]

            return cls(
                name=name,
                description=data.get('description', ''),
                coordinates=tuple(data.get('coordinates', [0, 0])),
                connected_area_names=data.get('connected_areas', []),
                inventory=inventory,
                npc_names=data.get('npcs', []),
                channel_id=data.get('channel_id'),
                allows_intercontinental_travel=data.get('allows_intercontinental_travel', False),
                danger_level=data.get('danger_level', 0)
            )
        except Exception as e:
            logging.error(f"Error creating Area from dict: {e}")
            raise

    def update(self, **kwargs: Any) -> None:
        """Update area attributes."""
        try:
            for key, value in kwargs.items():
                if key == 'inventory' and isinstance(value, list):
                    self.inventory = value
                elif key == 'npcs' and isinstance(value, list):
                    self.npcs = value
                elif key == 'connected_areas' and isinstance(value, list):
                    self.connected_areas = value
                elif hasattr(self, key):
                    setattr(self, key, value)
        except Exception as e:
            logging.error(f"Error updating Area {self.name}: {e}")

    def add_npc(self, npc: Any) -> bool:  # Runtime type: NPC
        """Add an NPC to the area."""
        try:
            if npc not in self.npcs:
                self.npcs.append(npc)
                return True
            return False
        except Exception as e:
            logging.error(f"Error adding NPC to Area {self.name}: {e}")
            return False

    def remove_npc(self, npc: Union[Any, str]) -> bool:  # Runtime type: Union[NPC, str]
        """Remove an NPC from the area."""
        try:
            if isinstance(npc, str):
                npc_obj = next((n for n in self.npcs if n.name == npc), None)
                if npc_obj:
                    self.npcs.remove(npc_obj)
                    return True
            elif npc in self.npcs:
                self.npcs.remove(npc)
                return True
            return False
        except Exception as e:
            logging.error(f"Error removing NPC from Area {self.name}: {e}")
            return False

    def add_item(self, item: Any) -> bool:  # Runtime type: Item
        """Add an item to the area's inventory."""
        try:
            if item not in self.inventory:
                self.inventory.append(item)
                return True
            return False
        except Exception as e:
            logging.error(f"Error adding item to Area {self.name}: {e}")
            return False

    def remove_item(self, item: Union[Any, str]) -> bool:  # Runtime type: Union[Item, str]
        """Remove an item from the area's inventory."""
        try:
            if isinstance(item, str):
                item_obj = next((i for i in self.inventory if i.name == item), None)
                if item_obj:
                    self.inventory.remove(item_obj)
                    return True
            elif item in self.inventory:
                self.inventory.remove(item)
                return True
            return False
        except Exception as e:
            logging.error(f"Error removing item from Area {self.name}: {e}")
            return False

    def connect_area(self, area: 'Area') -> bool:
        """Connect another area to this one."""
        try:
            if area not in self.connected_areas:
                self.connected_areas.append(area)
                # Ensure bidirectional connection
                if self not in area.connected_areas:
                    area.connected_areas.append(self)
                return True
            return False
        except Exception as e:
            logging.error(f"Error connecting areas {self.name} and {area.name}: {e}")
            return False

    def disconnect_area(self, area: 'Area') -> bool:
        """Disconnect another area from this one."""
        try:
            if area in self.connected_areas:
                self.connected_areas.remove(area)
                # Ensure bidirectional disconnection
                if self in area.connected_areas:
                    area.connected_areas.remove(self)
                return True
            return False
        except Exception as e:
            logging.error(f"Error disconnecting areas {self.name} and {area.name}: {e}")
            return False

    def get_npc(self, npc_name: str) -> Optional[Any]:  # Runtime type: Optional[NPC]
        """Get an NPC by name."""
        try:
            return next(
                (npc for npc in self.npcs if npc.name.lower() == npc_name.lower()),
                None
            )
        except Exception as e:
            logging.error(f"Error getting NPC {npc_name} from Area {self.name}: {e}")
            return None

    def __repr__(self) -> str:
        return f"<Area: {self.name} (Danger Level: {self.danger_level})>"