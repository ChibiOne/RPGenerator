# utils/game_objects/containers.py
from typing import Optional, List, Dict, Any
from .base import InventoryMixin
from .items import Item

class Container(InventoryMixin):
    """
    Class representing containers that can hold items.
    Inherits inventory management capabilities from InventoryMixin.
    """
    def __init__(
        self,
        name: str,
        inventory: Optional[List[Item]] = None,
        capacity: Optional[float] = None,
        description: str = '',
        locked: bool = False,
        **kwargs: Any
    ):
        """
        Initialize a container.
        
        Args:
            name: Container name
            inventory: Initial list of items
            capacity: Maximum weight capacity
            description: Container description
            locked: Initial lock status
            **kwargs: Additional arguments
        """
        super().__init__(inventory=inventory, capacity=capacity)
        self.name = name
        self.description = description
        self.capacity = capacity
        self.locked = locked

    def to_dict(self) -> Dict[str, Any]:
        """Convert container to dictionary format."""
        return {
            'name': self.name,
            'description': self.description,
            'capacity': self.capacity,
            'locked': self.locked,
            'inventory': [item.to_dict() for item in self.inventory if hasattr(item, 'to_dict')]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], item_lookup: Optional[Dict[str, Item]] = None) -> 'Container':
        """
        Create a container from dictionary data.
        
        Args:
            data: Dictionary containing container data
            item_lookup: Dictionary mapping item names to Item instances
        
        Returns:
            Container: New container instance
        """
        # Convert inventory data if item_lookup is provided
        inventory = None
        if item_lookup and 'inventory' in data:
            inventory = [
                item_lookup[item_name] for item_name in data['inventory']
                if item_name in item_lookup
            ]

        return cls(
            name=data['name'],
            inventory=inventory,
            capacity=data.get('capacity'),
            description=data.get('description', ''),
            locked=data.get('locked', False)
        )

    def lock(self) -> None:
        """Lock the container."""
        self.locked = True

    def unlock(self) -> None:
        """Unlock the container."""
        self.locked = False

    def can_access(self) -> bool:
        """Check if container can be accessed."""
        return not self.locked

    def __repr__(self) -> str:
        return f"<Container: {self.name} ({'locked' if self.locked else 'unlocked'})>"