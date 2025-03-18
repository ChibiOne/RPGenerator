# utils/character/equipment.py
import logging
from typing import Dict, Any, Optional, List, Tuple, cast
from dataclasses import dataclass, field

from ..game_objects.items import Item
from .types import ItemType, CharacterData, EquipmentSlotType

@dataclass
class EquipmentTemplate:
    """Template defining starting equipment for a character class.
    
    Attributes:
        right_hand (Optional[str]): Right hand weapon/item name
        left_hand (Optional[str]): Left hand weapon/item name
        armor (Optional[str]): Armor item name
        inventory_items (List[str]): List of starting inventory item names
    """
    right_hand: Optional[str] = None
    left_hand: Optional[str] = None
    armor: Optional[str] = None
    inventory_items: List[str] = field(default_factory=list)

class EquipmentManager:
    """Manages character equipment loading, validation, and operations.
    
    This class handles all equipment-related operations including:
    - Starting equipment assignment
    - Equipment validation
    - Equipment slot management
    - Equipment state verification
    """
    def __init__(self, item_manager: Any):
        """Initialize the equipment manager.
        
        Args:
            item_manager: The item manager instance for loading items
        """
        self.item_manager = item_manager
        self.class_templates = self._init_class_templates()
        logging.info("EquipmentManager initialized")

    def _init_class_templates(self) -> Dict[str, EquipmentTemplate]:
        """Initialize equipment templates for all character classes.
        
        Returns:
            Dict[str, EquipmentTemplate]: Mapping of class names to their equipment templates
        """
        return {
            "Warrior": EquipmentTemplate(
                right_hand="Longsword",
                left_hand="Wooden Shield",
                armor="Ringmail Armor",
                inventory_items=[
                    "Healing Potion",
                    "Bedroll",
                    "Tinderbox",
                    "Torch",
                    "Torch"
                ]
            ),
            "Mage": EquipmentTemplate(
                right_hand="Staff",
                left_hand="Dagger",
                armor="Robes",
                inventory_items=[
                    "Healing Potion",
                    "Bedroll",
                    "Tinderbox",
                    "Torch",
                    "Torch",
                    "Component Pouch"
                ]
            ),
            "Rogue": EquipmentTemplate(
                right_hand="Shortsword",
                left_hand="Dagger",
                armor="Leather Armor",
                inventory_items=[
                    "Healing Potion",
                    "Bedroll",
                    "Tinderbox",
                    "Torch",
                    "Torch",
                    "Thieves' Tools"
                ]
            ),
            "Cleric": EquipmentTemplate(
                right_hand="Mace",
                left_hand="Wooden Shield",
                armor="Chain Mail",
                inventory_items=[
                    "Healing Potion",
                    "Bedroll",
                    "Tinderbox",
                    "Torch",
                    "Torch",
                    "Holy Symbol"
                ]
            )
        }

    def get_starting_equipment(self, char_class: str) -> Tuple[Dict[str, Any], List[Item]]:
        """Get starting equipment for a character class.
        
        Args:
            char_class (str): The character's class name
            
        Returns:
            Tuple[Dict[str, Any], List[Item]]: Equipment and inventory items
            
        Raises:
            ValueError: If class template not found
        """
        try:
            template = self.class_templates.get(char_class)
            if not template:
                raise ValueError(f"No equipment template for class: {char_class}")

            equipment = {
                'Armor': None,
                'Left_Hand': None,
                'Right_Hand': None,
                'Belt_Slots': [None] * 4,
                'Back': None,
                'Magic_Slots': [None] * 3
            }

            # Load equipment items
            if template.right_hand:
                equipment['Right_Hand'] = self.item_manager.get_item(template.right_hand)
                logging.debug(f"Loaded right hand item: {template.right_hand}")
                
            if template.left_hand:
                equipment['Left_Hand'] = self.item_manager.get_item(template.left_hand)
                logging.debug(f"Loaded left hand item: {template.left_hand}")
                
            if template.armor:
                equipment['Armor'] = self.item_manager.get_item(template.armor)
                logging.debug(f"Loaded armor: {template.armor}")

            # Load inventory items
            inventory_items = []
            for item_name in template.inventory_items:
                item = self.item_manager.get_item(item_name)
                if item:
                    inventory_items.append(item)
                    logging.debug(f"Loaded inventory item: {item_name}")
                else:
                    logging.warning(f"Failed to load inventory item: {item_name}")

            return equipment, inventory_items

        except Exception as e:
            logging.error(f"Error getting starting equipment for {char_class}: {e}")
            return {}, []

    def validate_equipment(self, equipment: Dict[str, Any]) -> bool:
        """Validate equipment structure and items.
        
        Args:
            equipment (Dict[str, Any]): Equipment configuration to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            # Check required slots
            required_slots = {
                'Armor', 'Left_Hand', 'Right_Hand', 
                'Belt_Slots', 'Back', 'Magic_Slots'
            }
            
            if not all(slot in equipment for slot in required_slots):
                logging.error("Missing required equipment slots")
                return False

            # Validate slot types
            if not isinstance(equipment['Belt_Slots'], list) or len(equipment['Belt_Slots']) != 4:
                logging.error("Invalid Belt_Slots configuration")
                return False

            if not isinstance(equipment['Magic_Slots'], list) or len(equipment['Magic_Slots']) != 3:
                logging.error("Invalid Magic_Slots configuration")
                return False

            # Validate items in slots
            for slot, item in equipment.items():
                if isinstance(item, list):
                    for slot_item in item:
                        if slot_item is not None and not isinstance(slot_item, Item):
                            logging.error(f"Invalid item in {slot}")
                            return False
                elif item is not None and not isinstance(item, Item):
                    logging.error(f"Invalid item in {slot}")
                    return False

            return True

        except Exception as e:
            logging.error(f"Error validating equipment: {e}")
            return False

    def equip_item(self, equipment: Dict[str, Any], slot: str, item: Optional[Item]) -> bool:
        """Equip an item to a specific slot.
        
        Args:
            equipment (Dict[str, Any]): Equipment configuration
            slot (str): Target slot name
            item (Optional[Item]): Item to equip or None to unequip
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if slot not in equipment:
                logging.error(f"Invalid equipment slot: {slot}")
                return False

            if item is not None and not isinstance(item, Item):
                logging.error(f"Invalid item type for slot {slot}")
                return False

            equipment[slot] = item
            logging.info(f"{'Equipped' if item else 'Unequipped'} item in slot {slot}")
            return True

        except Exception as e:
            logging.error(f"Error equipping item to slot {slot}: {e}")
            return False

    def unequip_item(self, equipment: Dict[str, Any], slot: str) -> Optional[Item]:
        """Unequip an item from a specific slot.
        
        Args:
            equipment (Dict[str, Any]): Equipment configuration
            slot (str): Source slot name
            
        Returns:
            Optional[Item]: The unequipped item or None
        """
        try:
            if slot not in equipment:
                logging.error(f"Invalid equipment slot: {slot}")
                return None

            item = equipment[slot]
            equipment[slot] = None
            logging.info(f"Unequipped item from slot {slot}")
            return item

        except Exception as e:
            logging.error(f"Error unequipping item from slot {slot}: {e}")
            return None

__all__ = [
    'EquipmentTemplate',
    'EquipmentManager'
]