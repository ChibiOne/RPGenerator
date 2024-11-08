# utils/game_objects/character.py
import logging
import time
import asyncio
import random
from typing import Optional, Dict, List, Any, Tuple, Union

from .base import InventoryMixin
from .items import Item
from .world.area import Area
from config.settings import DEFAULT_STARTING_AREA
from utils.travel_system.conditions import TravelMode, WeatherEffect

class Character(InventoryMixin):
    """
    Represents a player character in the game world.
    
    Attributes:
        Base Info:
            user_id (str): Discord user ID
            name (str): Character name
            species (str): Character species/race
            char_class (str): Character class
            gender (str): Character gender
            pronouns (str): Preferred pronouns
            description (str): Character description
            
        Stats & Skills:
            stats (Dict[str, int]): Core ability scores
            skills (Dict[str, Any]): Character skills
            level (int): Character level
            xp (int): Experience points
            
        Inventory & Equipment:
            inventory (Dict[str, Item]): Character inventory
            equipment (Dict[str, Union[Item, List[Optional[Item]]]]): Equipped items
            currency (Dict[str, int]): Character currency
            capacity (float): Maximum carry weight
            
        Combat Stats:
            ac (int): Armor Class
            max_hp (int): Maximum hit points
            curr_hp (int): Current hit points
            movement_speed (int): Base movement speed
            
        Magic System:
            spells (Dict[str, Any]): Known spells
            spellslots (Dict[str, Any]): Available spell slots
            abilities (Dict[str, Any]): Special abilities
            
        Location & Travel:
            is_traveling (bool): Current travel status
            travel_end_time (Optional[float]): When travel completes
            current_area (Optional[Area]): Current area
            current_location (str): Current location name
            current_region (str): Current region name
            current_continent (str): Current continent name
            current_world (str): Current world name
            
        Guild Context:
            last_interaction_guild (Optional[int]): Last Discord guild ID
            area_lookup (Dict[str, Area]): Available areas
            reputation (Dict[str, int]): Faction standings
    """

    def __init__(self, user_id: str, name: Optional[str] = None, species: Optional[str] = None,
        char_class: Optional[str] = None, gender: Optional[str] = None, pronouns: Optional[str] = None,
        description: Optional[str] = None, stats: Optional[Dict[str, int]] = None, skills: Optional[Dict[str, Any]] = None,
        inventory: Optional[Dict[str, Item]] = None, equipment: Optional[Dict[str, Union[Item, List[Optional[Item]]]]] = None,
        currency: Optional[Dict[str, int]] = None, spells: Optional[Dict[str, Any]] = None, abilities: Optional[Dict[str, Any]] = None,
        ac: Optional[int] = None, max_hp: int = 1, curr_hp: int = 1, movement_speed: Optional[int] = None,
        travel_end_time: Optional[float] = None, spellslots: Optional[Dict[str, Any]] = None,
        level: Optional[int] = None, xp: Optional[int] = None, reputation: Optional[Dict[str, int]] = None,
        is_traveling: bool = False, current_area: Optional[Area] = None, current_location: Optional[str] = None,
        current_region: Optional[str] = None, current_continent: Optional[str] = None, current_world: Optional[str] = None,
        area_lookup: Optional[Dict[str, Area]] = None, capacity: Optional[float] = None,  **kwargs: Any
    ):
        """Initialize a new Character instance."""
        # Call InventoryMixin's __init__
        super().__init__(inventory=inventory, capacity=capacity or 150)

        logging.info(f"DEBUG: Character init inventory param type: {type(inventory)}")
        logging.info(f"DEBUG: Character init inventory param value: {inventory}")
        
        self.active_travel_mode: Optional[TravelMode] = None
        self.travel_destination: Optional['Area'] = None
        self.travel_party_id: Optional[str] = None
        self.last_interaction_guild = None
        self.last_travel_message = None
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.name = name
        self.species = species
        self.char_class = char_class
        self.gender = gender  
        self.pronouns = pronouns 
        self.description = description 
        self.stats = stats if stats else {
            'Strength': 10,
            'Dexterity': 10,
            'Constitution': 10,
            'Intelligence': 10,
            'Wisdom': 10,
            'Charisma': 10
        }
        capacity = capacity if capacity else 150

        self.skills = skills if skills else {}

        # Initialize inventory structure
        self.inventory = {}
        if inventory is not None:
            if isinstance(inventory, dict):
                for k, v in inventory.items():
                    if isinstance(v, Item):
                        self.inventory[k] = v
                    elif isinstance(v, dict):
                        try:
                            self.inventory[k] = Item.from_dict(v)
                        except Exception as e:
                            logging.error(f"Failed to convert inventory item: {e}")
                    else:
                        logging.warning(f"Unexpected inventory item type: {type(v)}")
            else:
                logging.error(f"Invalid inventory type provided: {type(inventory)}")


        # Initialize base equipment structure
        base_equipment = {
            'Armor': None,
            'Left_Hand': None,
            'Right_Hand': None,
            'Belt_Slots': [None] * 4,
            'Back': None,
            'Magic_Slots': [None] * 3
        }

        # Handle equipment initialization
        self.equipment = base_equipment
        if equipment:
            if isinstance(equipment, dict):
                for slot, item in equipment.items():
                    if slot not in base_equipment:
                        continue
                        
                    if isinstance(item, list):  # Handle Belt_Slots and Magic_Slots
                        converted_items = []
                        for slot_item in item:
                            if isinstance(slot_item, Item):
                                converted_items.append(slot_item)
                            elif isinstance(slot_item, dict):
                                try:
                                    converted_items.append(Item.from_dict(slot_item))
                                except Exception as e:
                                    logging.error(f"Failed to convert slot item: {e}")
                                    converted_items.append(None)
                            else:
                                converted_items.append(None)
                        self.equipment[slot] = converted_items
                    else:  # Handle regular slots
                        if isinstance(item, Item):
                            self.equipment[slot] = item
                        elif isinstance(item, dict):
                            try:
                                self.equipment[slot] = Item.from_dict(item)
                            except Exception as e:
                                logging.error(f"Failed to convert equipment item: {e}")
                                self.equipment[slot] = None
                        else:
                            self.equipment[slot] = None

        self.currency = currency if currency else {}
        self.spells = spells if spells else {}
        self.abilities = abilities if abilities else {}
        self.capacity = capacity
        self.ac = ac if ac else 5
        self.max_hp = max_hp if max_hp else 1
        self.curr_hp = curr_hp if curr_hp else 1
        self.movement_speed = movement_speed if movement_speed else 30
        self.travel_end_time = travel_end_time
        self.spellslots = spellslots
        self.level = level if level else 1
        self.xp = xp if xp else 0
        self.reputation = reputation if reputation else {}
        self.is_traveling = is_traveling if is_traveling else False
        self.current_area = current_area if current_area else area_lookup.get(DEFAULT_STARTING_AREA) if area_lookup else None
        self.current_location = current_location if current_location else "Northhold"
        self.current_region = current_region if current_region else "Northern Mountains"
        self.current_continent = current_continent if current_continent else "Aerilon"
        self.current_world = current_world if current_world else "Eldoria"
        
    def convert_equipment_item(item_data):
        """
        Converts equipment item data into an Item object.
        Args:
            item_data: Can be None, dict, or Item object
        Returns:
            Item or None: Converted item or None if invalid data
        """
        try:
            if not item_data:
                return None
                
            if isinstance(item_data, dict):
                # If we have valid item data as a dictionary
                return Item.from_dict(item_data)
            
            if hasattr(item_data, 'to_dict'):  # If it's already an Item object
                return item_data
                
            logging.warning(f"Unknown item data type: {type(item_data)}")
            return None
            
        except Exception as e:
            logging.error(f"Error converting equipment item: {e}")
            return None

    def to_dict(self):
        """Convert Character instance to a dictionary."""
        try:
            logging.info(f"Starting to_dict conversion for character {self.name}")
            
            # Handle inventory conversion
            logging.info("Converting inventory...")
            inventory_dict = {}
            if isinstance(self.inventory, dict):
                for k, v in self.inventory.items():
                    logging.info(f"Converting inventory item {k} of type {type(v)}")
                    if hasattr(v, 'to_dict'):
                        try:
                            inventory_dict[k] = v.to_dict()
                            logging.info(f"Successfully converted inventory item {k}")
                        except Exception as e:
                            logging.error(f"Error converting inventory item {k}: {e}")
                            inventory_dict[k] = str(v)
                    else:
                        inventory_dict[k] = str(v)

            # Handle equipment conversion
            logging.info("Converting equipment...")
            equipment_dict = {}
            if isinstance(self.equipment, dict):
                for slot, item in self.equipment.items():
                    logging.info(f"Converting equipment slot {slot} of type {type(item)}")
                    try:
                        if isinstance(item, list):
                            equipment_dict[slot] = []
                            for idx, i in enumerate(item):
                                if hasattr(i, 'to_dict'):
                                    try:
                                        equipment_dict[slot].append(i.to_dict())
                                        logging.info(f"Converted list item {idx} in slot {slot}")
                                    except Exception as e:
                                        logging.error(f"Error converting list item {idx} in slot {slot}: {e}")
                                        equipment_dict[slot].append(None)
                                else:
                                    equipment_dict[slot].append(None)
                        elif hasattr(item, 'to_dict'):
                            try:
                                equipment_dict[slot] = item.to_dict()
                                logging.info(f"Converted item in slot {slot}")
                            except Exception as e:
                                logging.error(f"Error converting item in slot {slot}: {e}")
                                equipment_dict[slot] = None
                        else:
                            equipment_dict[slot] = None
                    except Exception as e:
                        logging.error(f"Error processing slot {slot}: {e}")
                        equipment_dict[slot] = None

            logging.info("Creating base dictionary...")
            base_dict = {
                'User_ID': self.user_id,
                'Name': self.name,
                'Species': self.species,
                'Char_Class': self.char_class,
                'Gender': self.gender,
                'Pronouns': self.pronouns,
                'Description': self.description,
                'Stats': self.stats,
                'Skills': self.skills,
                'Inventory': inventory_dict,
                'Equipment': equipment_dict,
                'Currency': self.currency,
                'Spells': self.spells,
                'Abilities': self.abilities,
                'Capacity': self.capacity,
                'AC': self.ac,
                'Max_HP': self.max_hp,
                'Curr_HP': self.curr_hp,
                'Movement_Speed': self.movement_speed,
                'Travel_End_Time': self.travel_end_time,
                'Spellslots': self.spellslots,
                'Level': self.level,
                'XP': self.xp,
                'Reputation': self.reputation,
                'Is_Traveling': self.is_traveling,
                'Current_Area': self.current_area.name if self.current_area else None,
                'Current_Location': self.current_location,
                'Current_Region': self.current_region,
                'Current_Continent': self.current_continent,
                'Current_World': self.current_world,
                'Last_Interaction_Guild': self.last_interaction_guild
            }
            return base_dict

        except Exception as e:
            logging.error(f"Error converting Character to dict: {e}")
            logging.error(f"Error occurred at location: {e.__traceback__.tb_lineno}")
            logging.error(f"Error traceback: {e.__traceback__}")
            raise

    @classmethod
    def from_dict(cls, data, user_id, area_lookup=None, item_lookup=None):
        try:
            # Helper function to convert equipment data
            def convert_equipment_item(item_data, item_lookup):
                if not item_data:
                    return None
                return Item.from_dict(item_data) if isinstance(item_data, dict) else None

            # Convert equipment data
            equipment_data = data.get('Equipment', {})
            equipment = {
                'Armor': convert_equipment_item(equipment_data.get('Armor'), item_lookup),
                'Left_Hand': convert_equipment_item(equipment_data.get('Left_Hand'), item_lookup),
                'Right_Hand': convert_equipment_item(equipment_data.get('Right_Hand'), item_lookup),
                'Belt_Slots': [convert_equipment_item(item, item_lookup) 
                            for item in equipment_data.get('Belt_Slots', [None] * 4)],
                'Back': convert_equipment_item(equipment_data.get('Back'), item_lookup),
                'Magic_Slots': [convert_equipment_item(item, item_lookup) 
                            for item in equipment_data.get('Magic_Slots', [None] * 3)]
            }

            # Convert inventory data
            inventory_data = data.get('Inventory', {})
            inventory = {k: Item.from_dict(v) if isinstance(v, dict) else v 
                        for k, v in inventory_data.items()}

            # Convert travel_end_time
            travel_end_time = data.get('Travel_End_Time')

            # Get current area from area_lookup
            current_area_name = data.get('Current_Area')
            current_area = None
            if area_lookup and current_area_name:
                current_area = area_lookup.get(current_area_name)
                if not current_area:
                    logging.warning(f"Could not find area '{current_area_name}' in area_lookup")

            # Create and return new Character instance
            character = cls(
                user_id=user_id,
                name=data.get('Name'),
                species=data.get('Species'),
                char_class=data.get('Char_Class'),
                gender=data.get('Gender'),
                pronouns=data.get('Pronouns'),
                description=data.get('Description'),
                stats=data.get('Stats', {
                    'Strength': 10,
                    'Dexterity': 10,
                    'Constitution': 10,
                    'Intelligence': 10,
                    'Wisdom': 10,
                    'Charisma': 10
                }),
                skills=data.get('Skills', {}),
                inventory=inventory,
                equipment=equipment,
                currency=data.get('Currency', {}),
                spells=data.get('Spells', {}),
                abilities=data.get('Abilities', {}),
                ac=data.get('AC', 5),
                max_hp=data.get('Max_HP', 1),
                curr_hp=data.get('Curr_HP', 1),
                movement_speed=data.get('Movement_Speed', 30),
                travel_end_time=travel_end_time,
                spellslots=data.get('Spellslots'),
                level=data.get('Level', 1),
                xp=data.get('XP', 0),
                reputation=data.get('Reputation', {}),
                is_traveling=data.get('Is_Traveling', False),
                current_area=current_area,
                current_location=data.get('Current_Location', "Northhold"),
                current_region=data.get('Current_Region', "Northern Mountains"),
                current_continent=data.get('Current_Continent', "Aerilon"),
                current_world=data.get('Current_World', "Eldoria"),
                area_lookup=area_lookup,
                capacity=data.get('Capacity', 150)
            )
            
            # Add the guild ID after creation
            character.last_interaction_guild = data.get('Last_Interaction_Guild')
            
            return character
                
        except Exception as e:
            logging.error(f"Error creating Character from dict: {e}")
            return None

    def get_stat_modifier(self, stat):
        """
        Calculates the modifier for a given ability score.
        Args:
            stat (str): The name of the stat.
        Returns:
            int: The modifier.
        """
        return (self.stats.get(stat, 10) - 10) // 2
    
    def attack(self, target, weapon):
        """
        Perform an attack on a target using a weapon.
        Args:
            target (Character): The target character.
            weapon (Weapon): The weapon being used.
        Returns:
            str: The result of the attack.
        """
        # Calculate the attack roll
        attack_roll = random.randint(1, 20) + self.get_stat_modifier('Strength')
        # Calculate the damage roll
        damage_roll = random.randint(1, weapon.damage_amount) + self.get_stat_modifier('Strength')
        # Apply the damage to the target
        target.hp -= damage_roll
        return f"{self.name} attacks {target.name} with {weapon.name} for {damage_roll} damage."
    
    def use_consumable(self, item):
        # Apply the effect of the consumable
        # For example, if it's a healing potion
        effect = item.effect  # Assuming effect is a dict like {'heal': 10}
        result = ""
        if 'Heal' in effect:
            # Implement healing logic
            heal_amount = effect['Heal']
            # Assume character has 'current_hp' and 'max_hp' attributes
            self.current_hp = min(self.max_hp, self.current_hp + heal_amount)
            result = f"You have been healed for {heal_amount} HP."
        # Remove the item from inventory after use
        self.remove_item_from_inventory(item.name)
        return result

    def calculate_max_carry_weight(self):
        """
        Calculates the maximum weight the character can carry based on their strength score.
        Returns:
        int: The maximum weight in pounds.
        """
        strength = self.Stats.get('Strength', 10)
        return 15 * strength
    
    def equip_item(self, item, slot):
        if slot.startswith('Belt_Slot_'):
            index = int(slot.split('_')[-1]) - 1
            if 0 <= index < len(self.equipment['Belt_Slots']):
                if self.equipment['Belt_Slots'][index] is None:
                    self.equipment['Belt_Slots'][index] = item
                    self.remove_item_from_inventory(item.name)
                else:
                    raise ValueError(f"Belt_Slot {index+1} is already occupied.")
            else:
                raise ValueError("Invalid belt slot number.")
        elif slot.startswith('Magic_Slot_'):
            index = int(slot.split('_')[-1]) - 1
            if 0 <= index < len(self.equipment['Magic_Slots']):
                if self.equipment['Magic_Slots'][index] is None:
                    self.equipment['Magic_Slots'][index] = item
                    self.remove_item_from_inventory(item.name)
                else:
                    raise ValueError(f"Magic Slot {index+1} is already occupied.")
            else:
                raise ValueError("Invalid Magic Slot number.")
        elif slot in self.equipment:
            if self.equipment[slot] is None:
                self.equipment[slot] = item
                self.remove_item_from_inventory(item.name)
            else:
                raise ValueError(f"Slot {slot} is already occupied.")
        else:
            raise ValueError(f"Invalid equipment slot: {slot}.")

    def unequip_item(self, slot):
        if slot.startswith('belt_slot_'):
            index = int(slot.split('_')[-1]) - 1
            if 0 <= index < len(self.equipment['belt_slots']):
                item = self.equipment['belt_slots'][index]
                if item:
                    self.equipment['belt_slots'][index] = None
                    self.add_item_to_inventory(item)
                else:
                    raise ValueError(f"No item equipped in belt slot {index+1}.")
            else:
                raise ValueError("Invalid belt slot number.")
        elif slot.startswith('magic_slot_'):
            index = int(slot.split('_')[-1]) - 1
            if 0 <= index < len(self.equipment['magic_slots']):
                item = self.equipment['magic_slots'][index]
                if item:
                    self.equipment['magic_slots'][index] = None
                    self.add_item_to_inventory(item)
                else:
                    raise ValueError(f"No item equipped in magic slot {index+1}.")
            else:
                raise ValueError("Invalid magic slot number.")
        elif slot in self.equipment:
            if self.equipment[slot]:
                item = self.equipment[slot]
                self.equipment[slot] = None
                self.add_item_to_inventory(item)
            else:
                raise ValueError(f"No item equipped in slot {slot}.")
        else:
            raise ValueError(f"Invalid equipment slot: {slot}.")
        
    def move_to_area(self, new_area):
            """
            Moves the character to a new area.
            Args:
                new_area (Area): The new Area instance.
            Returns:
                bool: True if move successful, False otherwise
            """
            try:
                if not new_area:
                    logging.warning(f"Attempted to move character '{self.name}' to a non-existent area.")
                    return False

                if self.is_traveling:
                    logging.warning(f"Character '{self.name}' is currently traveling and cannot change areas.")
                    return False

                # Validate the move is allowed
                if (self.current_area and 
                    new_area not in self.current_area.connected_areas and 
                    not self.is_traveling):
                    logging.warning(f"Attempted to move character '{self.name}' to non-connected area '{new_area.name}'.")
                    return False

                old_area = self.current_area
                self.current_area = new_area
                logging.info(f"Character '{self.name}' moved from '{old_area.name if old_area else 'None'}' to '{new_area.name}'.")
                return True

            except Exception as e:
                logging.error(f"Error moving character '{self.name}' to new area: {e}")
                return False

    def move_to_location(self, new_location):
        """
        Move to a new location within the current region.
        """
        try:
            if not self.current_region:
                logging.warning(f"Character '{self.name}' has no current region.")
                return False

            if self.is_traveling:
                logging.warning(f"Character '{self.name}' is currently traveling.")
                return False

            if new_location not in self.current_region.locations:
                logging.warning(f"Location '{new_location}' not found in region '{self.current_region}'.")
                return False

            self.current_location = new_location
            
            # Find best default area in new location
            if new_location.areas:
                # Try to find a "central" or "main" area first
                default_area = next(
                    (area for area in new_location.areas if 
                    any(keyword in area.name.lower() for keyword in ['central', 'main', 'plaza', 'square'])),
                    new_location.areas[0]
                )
                self.current_area = default_area
            else:
                self.current_area = None
                logging.warning(f"No areas found in location '{new_location.name}'.")

            logging.info(f"Character '{self.name}' moved to location '{new_location.name}'.")
            return True

        except Exception as e:
            logging.error(f"Error moving character '{self.name}' to new location: {e}")
            return False

    def move_to_region(self, new_region):
        """
        Move to a new region within the current continent.
        """
        try:
            if not self.current_continent:
                logging.warning(f"Character '{self.name}' has no current continent.")
                return False

            if self.is_traveling:
                logging.warning(f"Character '{self.name}' is currently traveling.")
                return False

            if new_region not in self.current_continent.regions:
                logging.warning(f"Region '{new_region}' not found in continent '{self.current_continent}'.")
                return False

            self.current_region = new_region
            
            # Find best default location in new region
            if new_region.locations:
                # Try to find a "capital" or "main" location first
                default_location = next(
                    (loc for loc in new_region.locations if 
                     any(keyword in loc.name.lower() for keyword in ['capital', 'main', 'city', 'town'])),
                    new_region.locations[0]
                )
                self.move_to_location(default_location)
            else:
                logging.warning(f"No locations found in region '{new_region.name}'.")
                self.current_location = None
                self.current_area = None

            logging.info(f"Character '{self.name}' moved to region '{new_region.name}'.")
            return True

        except Exception as e:
            logging.error(f"Error moving character '{self.name}' to new region: {e}")
            return False

    def move_to_continent(self, new_continent):
        """
        Move to a new continent if at a valid port.
        """
        try:
            if not self.current_world or new_continent not in self.current_world.continents:
                logging.warning(f"Continent '{new_continent}' not found in world '{self.current_world}'.")
                return False

            if self.is_traveling:
                logging.warning(f"Character '{self.name}' is currently traveling.")
                return False

            if not (self.current_area and self.current_area.allows_intercontinental_travel):
                logging.warning(f"Character '{self.name}' must be at a port to travel between continents.")
                return False

            self.current_continent = new_continent

            # Find best default region in new continent
            if new_continent.regions:
                # Try to find a "starting" or "port" region first
                default_region = next(
                    (reg for reg in new_continent.regions if 
                     any(keyword in reg.name.lower() for keyword in ['port', 'harbor', 'coast', 'starting'])),
                    new_continent.regions[0]
                )
                self.move_to_region(default_region)
            else:
                logging.warning(f"No regions found in continent '{new_continent.name}'.")
                self.current_region = None
                self.current_location = None
                self.current_area = None

            logging.info(f"Character '{self.name}' moved to continent '{new_continent.name}'.")
            return True

        except Exception as e:
            logging.error(f"Error moving character '{self.name}' to new continent: {e}")
            return False

    async def start_travel(self, destination_area, travel_time):
        """
        Start traveling to a destination area.
        Args:
            destination_area (Area): The destination area
            travel_time (float): Travel time in seconds
        """
        try:
            if self.is_traveling:
                logging.warning(f"Character '{self.name}' is already traveling.")
                return False

            self.is_traveling = True
            self.travel_destination = destination_area
            current_time = time.time()
            self.travel_end_time = current_time + travel_time
            
            logging.info(f"Character '{self.name}' started traveling to '{destination_area.name}'.")
            
            # Start the travel task
            asyncio.create_task(
                travel_task(self, str(self.user_id), characters, save_characters)
            )
            return True

        except Exception as e:
            logging.error(f"Error starting travel for character '{self.name}': {e}")
            self.is_traveling = False
            self.travel_destination = None
            self.travel_end_time = None
            return False
        
    def equip_item(self, item, slot):
        """
        Attempt to equip an item to a slot
        Returns (success, message)
        """
        if not item.can_be_equipped(slot):
            return False, f"{item.Name} cannot be equipped in {slot}"

        if not item.check_proficiency(self):
            return False, f"You lack the proficiency to use {item.Name}"

        # Handle two-handed weapons
        if slot == 'Right_Hand' and item.Type == 'Weapon':
            if 'Two-Handed' in item.Effect:
                if self.equipment['Left_Hand']:
                    return False, "You need both hands free for this weapon"
                self.equipment['Left_Hand'] = None

        # Remove existing item if any
        old_item = self.equipment[slot]
        if old_item:
            old_item.remove_equip_effects(self)

        # Apply new item
        success = item.apply_equip_effects(self)
        if success:
            self.equipment[slot] = item
            return True, f"Equipped {item.Name} to {slot}"
        else:
            if old_item:
                old_item.apply_equip_effects(self)
                self.equipment[slot] = old_item
            return False, f"Failed to equip {item.Name}"

    def unequip_item(self, slot):
        """
        Unequip item from a slot
        Returns (success, message)
        """
        item = self.equipment[slot]
        if not item:
            return False, f"Nothing equipped in {slot}"

        item.remove_equip_effects(self)
        self.equipment[slot] = None
        return True, f"Unequipped {item.Name}"

    def use_item(self, item):
        """
        Use a consumable item
        Returns (success, message)
        """
        success, message = item.use_consumable(self)
        return success, message
    
    def get_effective_movement_speed(self, weather: Optional[WeatherEffect] = None) -> float:
        """Calculate actual movement speed with modifiers"""
        base_speed = self.movement_speed
        if weather:
            base_speed *= weather.speed_modifier
        # Add other modifiers (equipment, conditions, etc.)
        return base_speed

    def can_travel(self) -> Tuple[bool, str]:
        """Check if character can start traveling"""
        if self.is_traveling:
            return False, "Already traveling"
        if self.curr_hp <= 0:   
            return False, "Cannot travel while unconscious"
        return True, ""