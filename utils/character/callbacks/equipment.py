# utils/character/equipment.py
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
import logging
from ..items import Item

@dataclass
class EquipmentTemplate:
    """Template for class-specific starting equipment"""
    right_hand: Optional[str] = None
    left_hand: Optional[str] = None
    armor: Optional[str] = None
    inventory_items: List[str] = field(default_factory=list)

class EquipmentManager:
    def __init__(self, item_manager):
        self.item_manager = bot.item_manager
        self.class_templates = {
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
            # ... other class templates
        }

    def get_starting_equipment(self, char_class: str) -> tuple[Dict[str, Any], List[Item]]:
        """Get starting equipment for a character class"""
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
            if template.left_hand:
                equipment['Left_Hand'] = self.item_manager.get_item(template.left_hand)
            if template.armor:
                equipment['Armor'] = self.item_manager.get_item(template.armor)

            # Load inventory items
            inventory_items = [
                self.item_manager.get_item(item_name)
                for item_name in template.inventory_items
            ]

            # Filter out any None values from failed item loading
            inventory_items = [item for item in inventory_items if item is not None]

            return equipment, inventory_items

        except Exception as e:
            logging.error(f"Error getting starting equipment for {char_class}: {e}")
            return {}, []

    def validate_equipment(self, equipment: Dict[str, Any]) -> bool:
        """Validate equipment structure and items"""
        try:
            required_slots = {
                'Armor', 'Left_Hand', 'Right_Hand', 
                'Belt_Slots', 'Back', 'Magic_Slots'
            }
            
            if not all(slot in equipment for slot in required_slots):
                return False

            if not isinstance(equipment['Belt_Slots'], list) or len(equipment['Belt_Slots']) != 4:
                return False

            if not isinstance(equipment['Magic_Slots'], list) or len(equipment['Magic_Slots']) != 3:
                return False

            return True

        except Exception as e:
            logging.error(f"Error validating equipment: {e}")
            return False