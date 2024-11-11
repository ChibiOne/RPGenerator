# utils/game_objects/__init__.py

from typing import Dict, List, Optional, Any

# Base classes
from .base import Entity, InventoryMixin

# Core game objects
from .character import Character
from .npc import NPC
from .items import Item, Weapon, Armor, Shield

# World structure
from .world.area import Area
from .world.location import Location
from .world.region import Region
from .world.continent import Continent
from .world.world import World

__all__ = [
    # Base classes
    'Entity',
    'InventoryMixin',
    
    # Core game objects
    'Character',
    'NPC',
    'Item',
    'Weapon',
    'Armor',
    'Shield',
    
    # World structure
    'Area',
    'Location',
    'Region',
    'Continent',
    'World'
]