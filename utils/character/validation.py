# utils/character/validation.py
import re
import logging
from datetime import datetime
from typing import Tuple, Dict, Any, Optional, List, Union

from .types import (
    CharacterData,
    Stats,
    Equipment,
    SpeciesType,
    ClassType,
    StatType
)
from .constants import ABILITY_SCORE_COSTS, POINT_BUY_TOTAL
from ..game_objects.items import Item

class CharacterValidator:
    """Validates character data before creation and serialization."""
    
    VALID_SPECIES: List[SpeciesType] = ["Human", "Elf", "Dwarf", "Orc"]
    VALID_CLASSES: List[ClassType] = ["Warrior", "Mage", "Rogue", "Cleric"]
    VALID_STATS: List[StatType] = [
        "Strength", "Dexterity", "Constitution",
        "Intelligence", "Wisdom", "Charisma"
    ]
    
    @staticmethod
    def validate_name(name: str) -> Tuple[bool, str]:
        """Validates character name."""
        if not name:
            return False, "Name cannot be empty"
        if len(name) < 2:
            return False, "Name must be at least 2 characters"
        if len(name) > 32:
            return False, "Name must be 32 characters or less"
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9 -]*$', name):
            return False, "Name must start with a letter and contain only letters, numbers, spaces, and hyphens"
        return True, ""

    @staticmethod
    def validate_stats(stats: Stats) -> Tuple[bool, str]:
        """Validates character stats."""
        if not isinstance(stats, dict):
            return False, "Stats must be a dictionary"
            
        # Check all required stats are present
        for stat in CharacterValidator.VALID_STATS:
            if stat not in stats:
                return False, f"Missing required stat: {stat}"
                
        # Validate stat values and point buy
        total_cost = 0
        for stat, value in stats.items():
            if not isinstance(value, int):
                return False, f"{stat} must be an integer"
            if value < 8 or value > 15:
                return False, f"{stat} must be between 8 and 15"
            total_cost += ABILITY_SCORE_COSTS.get(value, 0)
            
        if total_cost != POINT_BUY_TOTAL:
            return False, f"Point buy total must be {POINT_BUY_TOTAL}, got {total_cost}"
            
        return True, ""

    @staticmethod
    def validate_equipment(equipment: Equipment) -> Tuple[bool, str]:
        """Validates character equipment."""
        if not isinstance(equipment, dict):
            return False, "Equipment must be a dictionary"
            
        required_slots = ["Armor", "Left_Hand", "Right_Hand", "Back"]
        for slot in required_slots:
            if slot not in equipment:
                return False, f"Missing required equipment slot: {slot}"
            
            item = equipment[slot]
            if item is not None and not isinstance(item, Item):
                return False, f"Invalid item type in slot {slot}"
                
        # Validate multi-item slots
        if "Belt_Slots" not in equipment or not isinstance(equipment["Belt_Slots"], list):
            return False, "Missing or invalid Belt_Slots"
        if len(equipment["Belt_Slots"]) != 4:
            return False, "Belt_Slots must have exactly 4 slots"
            
        if "Magic_Slots" not in equipment or not isinstance(equipment["Magic_Slots"], list):
            return False, "Missing or invalid Magic_Slots"
        if len(equipment["Magic_Slots"]) != 3:
            return False, "Magic_Slots must have exactly 3 slots"
            
        return True, ""

    @staticmethod
    def validate_inventory(inventory: Dict[str, Item]) -> Tuple[bool, str]:
        """Validates character inventory."""
        if not isinstance(inventory, dict):
            return False, "Inventory must be a dictionary"
            
        for key, item in inventory.items():
            if not isinstance(key, str):
                return False, "Inventory keys must be strings"
            if not isinstance(item, Item):
                return False, f"Invalid item type for {key}"
                
        return True, ""

    @staticmethod
    def validate_all(data: CharacterData) -> Tuple[bool, str]:
        """Validates all character data."""
        try:
            # Basic field validation
            if not data.get("user_id"):
                return False, "Missing user_id"
                
            name_valid, name_msg = CharacterValidator.validate_name(data.get("name", ""))
            if not name_valid:
                return False, name_msg
                
            if data.get("species") not in CharacterValidator.VALID_SPECIES:
                return False, f"Invalid species. Must be one of: {CharacterValidator.VALID_SPECIES}"
                
            if data.get("char_class") not in CharacterValidator.VALID_CLASSES:
                return False, f"Invalid class. Must be one of: {CharacterValidator.VALID_CLASSES}"
                
            if not data.get("gender"):
                return False, "Missing gender"
                
            if not data.get("pronouns"):
                return False, "Missing pronouns"
                
            if not data.get("description"):
                return False, "Missing description"

            # Complex field validation
            stats_valid, stats_msg = CharacterValidator.validate_stats(data.get("stats", {}))
            if not stats_valid:
                return False, f"Stats validation failed: {stats_msg}"
                
            equipment_valid, equipment_msg = CharacterValidator.validate_equipment(data.get("equipment", {}))
            if not equipment_valid:
                return False, f"Equipment validation failed: {equipment_msg}"
                
            inventory_valid, inventory_msg = CharacterValidator.validate_inventory(data.get("inventory", {}))
            if not inventory_valid:
                return False, f"Inventory validation failed: {inventory_msg}"

            # Timestamp validation
            if not isinstance(data.get("creation_date"), datetime):
                return False, "Invalid creation_date"
            if not isinstance(data.get("last_modified"), datetime):
                return False, "Invalid last_modified"

            # Guild ID validation
            guild_id = data.get("last_interaction_guild")
            if guild_id is not None and not isinstance(guild_id, int):
                return False, "Invalid guild_id type"

            return True, "All validations passed"
            
        except Exception as e:
            logging.error(f"Error during character validation: {e}", exc_info=True)
            return False, f"Validation error: {str(e)}"
