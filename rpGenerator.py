import discord
from discord.ext import commands
from discord.ui import View, Button, Select
from discord import SelectOption, Embed
from discord import app_commands
import json
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
import asyncio
import re
import logging
import random
import math
from datetime import datetime, timedelta

# ---------------------------- #
#        Configuration         #
# ---------------------------- #

# Load environment variables from .env file
load_dotenv()

# Discord and OpenAI API keys
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# File paths
CHARACTER_DATA_FILE = 'characters.json'
ACTIONS_FILE = 'actions.json'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# Initialize OpenAI Async Client
openai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,  # Optional if set via environment variable
)

# Define Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.dm_messages = True

# Initialize the bot
bot = commands.Bot(command_prefix='/', intents=intents)
tree = bot.tree  # Shortcut for command tree

# Initialize global variables
character_creation_sessions = {}
last_error_time = {}  # For global cooldowns per user
area_lookup = {}  # Dictionary mapping area names to Area instances
npc_lookup = {}  # Dictionary mapping NPC names to NPC instances
characters = {}  # Dictionary mapping user IDs to Character instances
actions = {}  # Dictionary mapping actions to their associated stats
my_world = None  # World instance


# ---------------------------- #
#          Utilities           #
# ---------------------------- #

def save_world(world, filename='world.json'):
    data = world.to_dict()
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def save_areas(areas, filename='areas.json'):
    data = {area.name: area.to_dict() for area in areas}
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def save_npcs(npcs, filename='npcs.json'):
    data = {npc.name: npc.to_dict() for npc in npcs}
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def load_world(filename='world.json'):
    with open(filename, 'r') as f:
        data = json.load(f)
    world = World.from_dict(data)
    return world


def load_npcs(filename='npcs.json'):
    with open(filename, 'r') as f:
        data = json.load(f)
    npc_lookup = {}
    for npc_name, npc_data in data.items():
        npc = NPC.from_dict(npc_data)
        npc_lookup[npc_name] = npc
    return npc_lookup

def assign_npcs_to_areas(area_lookup, npc_lookup):
    for area in area_lookup.values():
        area.npcs = [npc_lookup[npc_name] for npc_name in area.npc_names if npc_name in npc_lookup]


def calculate_distance(coord1, coord2):
    """Calculate distance between two coordinates."""
    return math.hypot(coord2[0] - coord1[0], coord2[1] - coord1[1])
    ## Assume area_1 and area_2 have coordinates
    #  distance = calculate_distance(area_1.coordinates, area_2.coordinates)
    #  print(f"The distance between {area_1.name} and {area_2.name} is {distance} units.")
    #  Output: The distance between Area 1 and Area 2 is 5.0 units.

def get_travel_time(character, destination_area):
    current_area = character.current_area
    distance = calculate_distance(current_area.coordinates, destination_area.coordinates)
    speed = character.movement_speed
    if speed == 0:
        return float('inf')  # Avoid division by zero
    travel_time = distance / speed
    return travel_time

async def travel_task(character, user_id, characters, save_characters):
    try:
        dt = datetime.utcnow()  # Use UTC to avoid timezone issues
        seconds = dt.timestamp()
        travel_duration = character.travel_end_time - seconds

        # Ensure travel_duration is non-negative
        if travel_duration > 0:
            await asyncio.sleep(travel_duration)
        else:
            logging.warning(f"Negative or zero travel duration for user '{user_id}'. Skipping sleep.")

        # Update character's status
        character.is_traveling = False
        character.move_to_area(character.travel_destination)
        character.travel_destination = None
        character.travel_end_time = None

        # Update the global 'characters' dictionary
        characters[user_id] = character

        # Save the updated 'characters' dictionary
        save_characters(characters)

        # Notify the user of arrival
        user = bot.get_user(int(user_id))
        if user:
            await user.send(f"You have arrived at **{character.current_area.name}**.")

        logging.info(f"User '{user_id}' has arrived at '{character.current_area.name}'.")
    
    except Exception as e:
        logging.error(f"Error in travel_task for user '{user_id}': {e}")

def load_actions():
    """
    Loads actions from the actions.json file.
    Returns:
        dict: A dictionary mapping actions to their associated stats.
    """
    try:
        with open(ACTIONS_FILE, 'r') as f:
            global actions
            actions = json.load(f)
            logging.info("actions.json loaded successfully.")
            return actions
    except FileNotFoundError:
        logging.error("actions.json file not found.")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding actions.json: {e}")
        return {}
    
def loadall():
    # Load world structure
    my_world = load_world()
    # Load areas
    area_lookup = load_areas()
    # Load NPCs
    npc_lookup = load_npcs()
    # Assign NPCs to areas
    assign_npcs_to_areas(area_lookup, npc_lookup)
    # Load characters
    characters = load_characters(area_lookup)

def saveall():
    # Collect all areas and NPCs
    areas = []  # List of all Area instances
    npcs = []     # List of all NPC instances
    # Save world structure
    save_world(my_world)
    # Save areas
    save_areas(areas)
    # Save NPCs
    save_npcs(npcs)
    # Save characters
    save_characters(characters)

actions = load_actions()

######################
#    Game Objects    #
######################

# Dictionary mapping channel IDs to Area instances
channel_areas = {}

def get_area_by_channel(channel_id):
    return channel_areas.get(channel_id)

def get_area_inventory(channel_id):
    """Get or create the inventory for the area associated with a channel."""
    if channel_id not in channel_areas:
        channel_areas[channel_id] = []
    return channel_areas[channel_id]

class Item:
    def __init__(self, name, weight, item_type, description='', effect=None,
                 proficiency_needed=None, average_cost=0, is_magical=False, rarity='Common'):
        self.name = name
        self.weight = weight
        self.item_type = item_type  # e.g., 'Weapon', 'Armor', 'Consumable'
        self.description = description
        self.effect = effect  # Can be a string or a dictionary describing the effect
        self.proficiency_needed = proficiency_needed
        self.average_cost = average_cost
        self.is_magical = is_magical
        self.rarity = rarity  # e.g., 'Common', 'Uncommon', 'Rare', etc.

    def to_dict(self):
        return {
            'name': self.name,
            'weight': self.weight,
            'item_type': self.item_type,
            'description': self.description,
            'effect': self.effect,
            'proficiency_needed': self.proficiency_needed,
            'average_cost': self.average_cost,
            'is_magical': self.is_magical,
            'rarity': self.rarity
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            weight=data['weight'],
            item_type=data['item_type'],
            description=data.get('description', ''),
            effect=data.get('effect'),
            proficiency_needed=data.get('proficiency_needed'),
            average_cost=data.get('average_cost', 0),
            is_magical=data.get('is_magical', False),
            rarity=data.get('rarity', 'Common')
        )

class InventoryMixin:
    def __init__(self, inventory=None, capacity=None):
        self.inventory = inventory if inventory is not None else []
        self.capacity = capacity

    def add_item_to_inventory(self, item: Item) -> None:
        if not isinstance(item, Item):
            raise TypeError("Only items of type 'Item' can be added to the inventory.")
        if self.can_add_item(item):
            self.inventory.append(item)
            print(f"Added {item.name} to {self.__class__.__name__}'s inventory.")
        else:
            print(f"Cannot add {item.name}; inventory is full.")

    def remove_item_from_inventory(self, item_name):
        for item in self.inventory:
            if item.name == item_name:
                self.inventory.remove(item)
                print(f"Removed {item.name} from {self.__class__.__name__}'s inventory.")
                return item
        print(f"Item {item_name} not found in inventory.")
        return None

    def can_add_item(self, item):
        if self.capacity is None:
            return True  # Unlimited capacity

        current_weight = self.calculate_total_weight()
        if current_weight + item.weight <= self.capacity:
            return True
        else:
            return False

    def calculate_total_weight(self):
        return sum(item.weight for item in self.inventory)
    
    def transfer_item(from_entity, to_entity, item_name):
        item = from_entity.remove_item_from_inventory(item_name)
        if item:
            if to_entity.can_add_item(item):
                to_entity.add_item_to_inventory(item)
                print(f"Transferred {item.name} from {from_entity.name} to {to_entity.name}.")
            else:
                # Return item to original entity if transfer fails
                from_entity.add_item_to_inventory(item)
                print(f"Cannot transfer {item.name}; {to_entity.name}'s inventory is full.")

class Weapon(Item):
    def __init__(self, damage_amount, damage_type, **kwargs):
        super().__init__(item_type='Weapon', **kwargs)
        self.damage_amount = damage_amount
        self.damage_type = damage_type
        self.effect = {'damage': self.damage_amount, 'type': self.damage_type}
    
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'damage_amount': self.damage_amount,
            'damage_type': self.damage_type
        })
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            weight=data['weight'],
            description=data.get('description', ''),
            effect=data.get('effect'),
            proficiency_needed=data.get('proficiency_needed'),
            average_cost=data.get('average_cost', 0),
            is_magical=data.get('is_magical', False),
            rarity=data.get('rarity', 'Common'),
            damage_amount=data['damage_amount'],
            damage_type=data['damage_type']
        )

class Armor(Item):
    def __init__(self, ac_value, max_dex_bonus, **kwargs):
        super().__init__(item_type='Armor', **kwargs)
        self.ac_value = ac_value
        self.max_dex_bonus = max_dex_bonus
        self.effect = {'AC': self.ac_value, 'dexBonus': self.max_dex_bonus}
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'ac_value': self.ac_value,
            'max_dex_bonus': self.max_dex_bonus
        })
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            weight=data['weight'],
            description=data.get('description', ''),
            effect=data.get('effect'),
            proficiency_needed=data.get('proficiency_needed'),
            average_cost=data.get('average_cost', 0),
            is_magical=data.get('is_magical', False),
            rarity=data.get('rarity', 'Common'),
            ac_value=data['ac_value'],
            max_dex_bonus=data['max_dex_bonus']
        )

class Shield(Item):
    def __init__(self, ac_value, max_dex_bonus, **kwargs):
        super().__init__(item_type='Shield', **kwargs)
        self.ac_value = ac_value
        self.effect = {'AC': self.ac_value}
    
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'ac_value': self.ac_value,
        })
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            weight=data['weight'],
            description=data.get('description', ''),
            effect=data.get('effect'),
            proficiency_needed=data.get('proficiency_needed'),
            average_cost=data.get('average_cost', 0),
            is_magical=data.get('is_magical', False),
            rarity=data.get('rarity', 'Common'),
            ac_value=data['ac_value'],
            max_dex_bonus=data['max_dex_bonus']
        )


class Container(InventoryMixin):
    def __init__(self, name, inventory=None, capacity=None, description='',locked=False, **kwargs):
        super().__init__(inventory=inventory, capacity=capacity)
        self.name = name
        self.description = description
        self.capacity = capacity
        self.locked = False
        # Additional attributes if needed

class World:
    def __init__(self, name, description='', continents=None, coordinates=(0, 0)):
        self.coordinates = coordinates  # (x, y)
        self.name = name
        self.description = description
        self.continents = continents if continents is not None else []

    def add_continent(self, continent, coordinates):
        self.continents.append(continent,coordinates)
    
    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'continents': self.continent_names
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            description=data.get('description', ''),
            continents=None  # Will be set after loading Continents
        )

class Continent:
    def __init__(self, name, description='', regions=None, coordinates=(0, 0)):
        self.coordinates = coordinates  # (x, y)
        self.name = name
        self.description = description
        self.regions = regions if regions is not None else []

    def add_region(self, region, coordinates):
        self.regions.append(region, coordinates)
    
    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'coordinates': self.coordinates,
            'regions': self.region_names
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            description=data.get('description', ''),
            coordinates=tuple(data.get('coordinates', (0, 0))),
            regions=None  # Will be set after loading Regions
        )

class Region:
    def __init__(self, name, description='', locations=None, coordinates=(0, 0)):
        self.coordinates = coordinates  # (x, y)
        self.name = name
        self.description = description
        self.locations = locations if locations is not None else []

    def add_location(self, location, coordinates):
        self.locations.append(location, coordinates)
    
    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'coordinates': self.coordinates,
            'locations': self.location_names
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            description=data.get('description', ''),
            coordinates=tuple(data.get('coordinates', (0, 0))),
            locations=None  # Will be set after loading Locations
        )

class Location:
    def __init__(self, name, description='', areas=None, coordinates=(0, 0)):
        self.coordinates = coordinates  # (x, y)
        self.name = name
        self.description = description
        self.areas = areas if areas is not None else []

    def add_area(self, area, coordinates):
        self.areas.append(area,coordinates)
    
    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'coordinates': self.coordinates,
            'areas': self.area_names
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            description=data.get('description', ''),
            coordinates=tuple(data.get('coordinates', (0, 0))),
            areas=None  # Will be set after loading Areas
        )

class Area:
    def __init__(self, name, description, inventory=None, connected_areas=None, coordinates=(0, 0), channel_id=None, npcs=None):
        self.name = name
        self.description = description
        self.inventory = inventory if inventory else []
        self.connected_areas = connected_areas if connected_areas else []  # List of Area instances
        self.coordinates = coordinates
        self.channel_id = channel_id
        self.npcs = npcs if npcs else []

    
    def add_npc(self, npc):
        if npc not in self.npcs:
            self.npcs.append(npc)
    
    def remove_npc(self, npc_name):
        for npc in self.npcs:
            if npc.name == npc_name:
                self.npcs.remove(npc)
                return npc
        return None  # NPC not found

    def add_connected_area(self, area, bidirectional=True, coordinates=(0, 0)):
        if area not in self.connected_areas:
            self.connected_areas.append(area,coordinates)
            area.connected_areas.append(self)  # Assuming bidirectional connection
    
    def get_npc(self, npc_name):
        for npc in self.npcs:
            if npc.name.lower() == npc_name.lower():
                return npc
        return None
    
    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'inventory': [item.to_dict() for item in self.inventory],
            'npcs': [npc.to_dict() for npc in self.npcs],
            'coordinates': self.coordinates,
            'connected_areas': [area.name for area in self.connected_areas],
            'channel_id': self.channel_id,
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            description=data.get('description', ''),
            inventory=[Item.from_dict(item) for item in data.get('inventory', [])],
            connected_areas=data.get('connected_areas', []),
            coordinates=tuple(data.get('coordinates', (0, 0))),
            channel_id=data.get('channel_id'),
            npcs=[NPC.from_dict(npc) for npc in data.get('npcs', [])]
        )
        # Load NPCs
        area.npcs = [NPC.from_dict(npc_data) for npc_data in data.get('npcs', [])]
        area.connected_area_names = data.get('connected_areas', [])
        return area

def load_areas(filename='areas.json'):
    with open(filename, 'r') as f:
        data = json.load(f)
    
    area_lookup = {}
    
    # First pass: create Area instances without setting connected_areas
    for area_name, area_data in data.items():
        area = Area.from_dict(area_data)
        area_lookup[area_name] = area
    
    # Second pass: resolve connected_areas to Area instances
    for area in area_lookup.values():
        # Replace connected area names with Area objects
        resolved_connected_areas = []
        for connected_area_name in area.connected_areas:
            connected_area = area_lookup.get(connected_area_name)
            if connected_area:
                resolved_connected_areas.append(connected_area)
            else:
                print(f"Warning: Connected area '{connected_area_name}' not found for area '{area.name}'.")
        area.connected_areas = resolved_connected_areas
    
    return area_lookup

    
# Load areas
area_lookup = load_areas()

# Function to retrieve an Area by name
def get_area_by_name(area_name, area_lookup):
    area = area_lookup.get(area_name)
    if not area:
        raise ValueError(f"Area '{area_name}' does not exist.")
    return area


class Entity(InventoryMixin):
    def __init__(self, name, stats=None, inventory=None, **kwargs):
        self.name = name
        self.stats = stats if stats else {}
        # Other shared attributes...

    def get_stat_modifier(self, stat):
        return (self.stats.get(stat, 10) - 10) // 2

class Character(Entity):
    """
    Represents a player's character with various attributes.
    """
    def __init__(self, user_id, name = None, species=None, char_class=None, gender=None, pronouns=None, description=None, stats=None, skills=None, inventory=None, equipment=None, currency=None, spells=None, abilities=None, ac = None, max_hp = 1, curr_hp = 1, movement_speed = None, travel_end_time = None, spellslots = None, level=None, xp=None, reputation=None, is_traveling = False, current_area=None, current_location=None, current_region=None, current_continent=None, current_world=None, **kwargs):
        self.user_id = user_id
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
        self.skills = skills if skills else {}
        self.inventory = kwargs.get('inventory', [])
        self.equipment = kwargs.get('equipment', {
            'armor': None,
            'left_hand': None,
            'right_hand': None,
            'belt_slots': [None]*4,
            'back': None,
            'magic_slots': [None]*3
        })
        self.currency = currency if currency else {}
        self.spells = spells if spells else {}
        self.abilities = abilities if abilities else {}
        self.capacity = self.calculate_max_carry_weight()
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
        # Location attributes
        if current_area and not isinstance(current_area, Area):
            raise TypeError("current_area must be an Area instance or None.")
        self.current_area = current_area if current_area else area_lookup.get("Clearing")
        self.current_area = current_area if current_area else None
        self.current_area_name = current_area.name if current_area else area_lookup.get("Clearing")
        self.current_location = current_location if current_location else None
        self.current_region = current_region if current_region else None
        self.current_continent = current_continent if current_continent else None
        self.current_world = current_world if current_world else None

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
        if 'heal' in effect:
            # Implement healing logic
            heal_amount = effect['heal']
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
        strength = self.stats.get('Strength', 10)
        return 15 * strength
    
    def equip_item(self, item, slot):
        if slot.startswith('belt_slot_'):
            index = int(slot.split('_')[-1]) - 1
            if 0 <= index < len(self.equipment['belt_slots']):
                if self.equipment['belt_slots'][index] is None:
                    self.equipment['belt_slots'][index] = item
                    self.remove_item_from_inventory(item.name)
                else:
                    raise ValueError(f"Belt slot {index+1} is already occupied.")
            else:
                raise ValueError("Invalid belt slot number.")
        elif slot.startswith('magic_slot_'):
            index = int(slot.split('_')[-1]) - 1
            if 0 <= index < len(self.equipment['magic_slots']):
                if self.equipment['magic_slots'][index] is None:
                    self.equipment['magic_slots'][index] = item
                    self.remove_item_from_inventory(item.name)
                else:
                    raise ValueError(f"Magic slot {index+1} is already occupied.")
            else:
                raise ValueError("Invalid magic slot number.")
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
        if new_area in self.current_area.connected_areas:
            self.current_area = new_area
            # Update current location if necessary
            return True
        else:
            return False
    
    def move_to_location(self, new_location):
        # Check if new_location is adjacent or accessible from current location
        # For simplicity, assume any location within the same region is accessible
        if new_location in self.current_region.locations:
            self.current_location = new_location
            # Update current area to a default area in the new location
            self.current_area = new_location.areas[0] if new_location.areas else None
            return True
        else:
            return False
        
    def move_to_region(self, new_region):
        # Check if new_region is adjacent or accessible from current region
        # For simplicity, assume any region within the same continent is accessible
        if new_region in self.current_continent.regions:
            self.current_region = new_region
            # Update current location and area
            self.current_location = new_region.locations[0] if new_region.locations else None
            self.current_area = self.current_location.areas[0] if self.current_location and self.current_location.areas else None
            return True
        else:
            return False
        
    def move_to_continent(self, new_continent):
        # Implement conditions for moving between continents (e.g., must be at a port)
        if new_continent in self.current_world.continents:
            # Check if the character is at a port area that allows intercontinental travel
            if self.current_area and self.current_area.allows_intercontinental_travel:
                self.current_continent = new_continent
                # Update current region, location, and area
                self.current_region = new_continent.regions[0] if new_continent.regions else "Avaloria"
                self.current_location = self.current_region.locations[0] if self.current_region and self.current_region.locations else ""
                self.current_area = self.current_location.areas[0] if self.current_location and self.current_location.areas else None
                return True
            else:
                print("You must be at a port to travel between continents.")
                return False
        else:
            return False

    async def start_travel(self, destination_area, travel_time):
        self.is_traveling = True
        self.travel_destination = destination_area
        user_id = self.user_id
        dt = datetime.today()  # Get timezone naive now
        seconds = dt.timestamp()
        self.travel_end_time = seconds + (timedelta(hours=travel_time).total_seconds())
        # Start the travel task
        asyncio.create_task(travel_task(self, user_id, characters, save_characters))

    def to_dict(self):
        return {
            'name': self.name,
            'species': self.species,
            'char_class': self.char_class,
            'stats': self.stats,
            'inventory': [item.to_dict() for item in self.inventory],
            'equipment': {
                'armor': self.equipment['armor'].to_dict() if self.equipment['armor'] else None,
                'left_hand': self.equipment['left_hand'].to_dict() if self.equipment['left_hand'] else None,
                'right_hand': self.equipment['right_hand'].to_dict() if self.equipment['right_hand'] else None,
                'belt_slots': [item.to_dict() if item else None for item in self.equipment['belt_slots']],
                'back': self.equipment['back'].to_dict() if self.equipment['back'] else None,
                'magic_slots': [item.to_dict() if item else None for item in self.equipment['magic_slots']]
            },
            'capacity': self.capacity,
            'ac': self.ac,
            'max_hp': self.max_hp,
            'curr_hp': self.curr_hp,
            'movement_speed': self.movement_speed,
            'travel_end_time': self.travel_end_time,
            'spellslots': self.spellslots,
            'level': self.level,
            'xp': self.xp,
            'reputation': self.reputation,
            'current_area_name': self.current_area.name if self.current_area else None,
            'current_location': self.current_location,
            'current_region': self.current_region,
            'current_continent': self.current_continent,
            'current_world': self.current_world
            }
        

    @classmethod
    def from_dict(cls, data, user_id, area_lookup):
        inventory = [Item.from_dict(item_data) for item_data in data.get('inventory', [])]
        equipment_data = data.get('equipment', {})
        equipment = {
            'armor': Item.from_dict(equipment_data['armor']) if equipment_data.get('armor') else None,
            'left_hand': Item.from_dict(equipment_data['left_hand']) if equipment_data.get('left_hand') else None,
            'right_hand': Item.from_dict(equipment_data['right_hand']) if equipment_data.get('right_hand') else None,
            'belt_slots': [Item.from_dict(item) if item else None for item in equipment_data.get('belt_slots', [None]*4)],
            'back': Item.from_dict(equipment_data['back']) if equipment_data.get('back') else None,
            'magic_slots': [Item.from_dict(item) if item else None for item in equipment_data.get('magic_slots', [None]*3)]
        }
        current_area_name = data.get('current_area_name')
        current_area = area_lookup.get(current_area_name) if current_area_name else None
        return cls(
            name=data['name'],
            user_id=user_id,
            species=data.get('species'),
            char_class=data.get('char_class'),
            stats=data.get('stats', {}),
            inventory=inventory,
            equipment=equipment,
            level=data.get('level'),
            xp=data.get('xp'),
            reputation=data.get('reputation'),
            ac=data.get('ac'),
            max_hp=data.get('max_hp'),
            curr_hp=data.get('curr_hp'),
            movement_speed=data.get('movement_speed'),
            travel_end_time=data.get('travel_end_time'),
            spellslots=data.get('spellslots'),
            current_area=current_area,
            current_location=data.get('current_location') if data.get('current_location') else "Unknown",
            current_region=data.get('current_region') if data.get('current_region') else "Avaloria",
            current_continent=data.get('current_continent') if data.get('current_continent') else "Eldoria",
            current_world=data.get('current_world') if data.get('current_world') else "Endara"
        )


def check_travel_completion(character):
    if character.is_traveling:
        dt = datetime.today()  # Get timezone naive now
        seconds = dt.timestamp()
        if seconds >= character.travel_end_time:
            character.is_traveling = False
            character.move_to_area(character.travel_destination)
            character.travel_destination = None
            character.travel_end_time = None
            return True  # Travel completed
    return False  # Still traveling


def load_characters(area_lookup, filename='characters.json'):
    """
    Loads character data from the characters.json file.
    Returns:
        dict: A dictionary mapping user IDs to Character instances.
    """
    try:
            with open(filename, 'r') as f:
                data = json.load(f)
                characters = {}
            for user_id, char_data in data.items():
                character = Character.from_dict(char_data, area_lookup=area_lookup, user_id=user_id)
                # Set current area reference
                area_name = character.current_area_name
                character.current_area = area_lookup.get(area_name)
                characters[user_id] = character
            return characters
    except FileNotFoundError:
        logging.error("characters.json file not found.")
        return {}

def save_characters(characters, filename='characters.json'):
    if not isinstance(characters, dict):
        logging.error("Invalid data type for 'characters'. Expected a dictionary.")
        return
    try:
        data = {user_id: character.to_dict() for user_id, character in characters.items()}
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        logging.info("Characters saved successfully.")
    except Exception as e:
        logging.error(f"Failed to save characters: {e}")


characters = load_characters(area_lookup)

# Point-Buy System Configuration
POINT_BUY_TOTAL = 27
ABILITY_SCORE_COSTS = {
    8: -2,  # Lowering to 8 gains 2 points
    9: -1,  # Lowering to 9 gains 1 point
    10: 0,  # Base score, no cost
    11: 1,
    12: 2,
    13: 3,
    14: 5,
    15: 7
}

def calculate_score_cost(score):
    """
    Returns the point cost for a given ability score based on the point-buy system.
    Args:
        score (int): The ability score.
    Returns:
        int: The point cost.
    Raises:
        ValueError: If the score is not between 8 and 15 inclusive.
    """
    if score not in ABILITY_SCORE_COSTS:
        raise ValueError(f"Invalid ability score: {score}. Must be between 8 and 15.")
    return ABILITY_SCORE_COSTS[score]

def is_valid_point_allocation(allocation):
    """
    Validates if the total points spent/gained in the allocation meet the point-buy criteria.
    Args:
        allocation (dict): A dictionary of ability scores.
    Returns:
        tuple: (bool, str) indicating validity and a message.
    """
    try:
        total_cost = sum(calculate_score_cost(score) for score in allocation.values())
    except ValueError as e:
        return False, str(e)
    
    # Calculate the minimum total cost based on possible point gains from lowering scores
    max_points_gained = 2 * list(allocation.values()).count(8) + 1 * list(allocation.values()).count(9)
    min_total_cost = POINT_BUY_TOTAL - max_points_gained
    
    if total_cost > POINT_BUY_TOTAL:
        return False, f"Total points spent ({total_cost}) exceed the allowed pool of {POINT_BUY_TOTAL}."
    elif total_cost < POINT_BUY_TOTAL:
        return False, f"Total points spent ({total_cost}) are less than the allowed pool of {POINT_BUY_TOTAL}."

    if total_cost < min_total_cost:
        return False, f"Total points spent ({total_cost}) are too low. Ensure you spend exactly {POINT_BUY_TOTAL} points."
        for score in allocation.values():
            if score < 8 or score > 15:
                return False, f"Ability scores must be between 8 and 15. Found {score}."
    return True, "Valid allocation."



class NPC(Entity):
    def __init__(self=None, name = None, role = None, inventory=None, capacity=None, stats = None, movement_speed = None, travel_end_time = None, max_hp = None, curr_hp = None, spellslots = None, ac = None,abilities = None, spells = None, attitude = None, faction = None, reputation = None, relations = None, dialogue = None, description = None, is_hostile = None, current_area = None, **kwargs):
        super().__init__(inventory=inventory, capacity=capacity)
        self.name = name
        self.role = role # e.g., 'Shopkeeper', 'Guard', 'Quest Giver'
        self.stats = stats
        self.movement_speed = movement_speed
        self.travel_end_time = travel_end_time
        self.max_hp = max_hp
        self.curr_hp = curr_hp
        self.spellslots = spellslots
        self.ac = ac
        self.abilities = abilities
        self.spells = spells
        self.attitude = attitude
        self.faction = faction
        self.reputation = reputation
        self.relations = relations
        self.dialogue = dialogue if dialogue else {}
        self.description = description
        self.is_hostile = is_hostile if is_hostile is not None else False
        self.current_area = current_area if current_area else "The Void"

    def move_to_area(self, new_area):
        if self.current_area:
            self.current_area.remove_npc(self.name)
        self.current_area = new_area
        new_area.add_npc(self)
    
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
        target.curr_hp -= damage_roll
        return f"{self.name} attacks {target.name} with {weapon.name} for {damage_roll} damage."
    
    def get_dialogue(self):
        if self.dialogue:
            return self.dialogue.pop(0)  # Return the next dialogue line
        else:
            return f"{self.name} has nothing more to say."
    
    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'dialogue': self.dialogue,
            'inventory': [item.to_dict() for item in self.inventory],
            'stats': self.stats,
            'is_hostile': self.is_hostile,
            'role': self.role,
            'movement_speed': self.movement_speed,
            'travel_end_time': self.travel_end_time,
            'max_hp': self.max_hp,
            'curr_hp': self.curr_hp,
            'spellslots': self.spellslots,
            'ac': self.ac,
            'abilities': self.abilities,
            'spells': self.spells,
            'attitude': self.attitude,
            'faction': self.faction,
            'reputation': self.reputation,
            'relations': self.relations
        }

    @classmethod
    def from_dict(cls, data):
        npc = cls(
            name=data['name'],
            description=data.get('description', ''),
            dialogue=data.get('dialogue', []),
            inventory=[Item.from_dict(item_data) for item_data in data.get('inventory', [])],
            stats=data.get('stats', {}),
            is_hostile=data.get('is_hostile', False),
        )
        return npc
       # Additional NPC-specific attributes



# ---------------------------- #
#      UI Component Classes    #
# ---------------------------- #

class GenericDropdown(discord.ui.Select):
    """
    A generic dropdown class that can be reused for various selections.
    """
    def __init__(self, placeholder, options, callback_func, user_id):
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)
        self.callback_func = callback_func
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await self.callback_func(self, interaction, self.user_id)

# Callback functions for dropdowns
async def gender_callback(dropdown, interaction, user_id):
    """
    Callback for gender selection.
    """
    try:
        selected_gender = dropdown.values[0]
        character_creation_sessions[user_id]['gender'] = selected_gender
        logging.info(f"User {user_id} selected gender: {selected_gender}")

        # Proceed to pronouns selection
        await interaction.response.edit_message(
            content=f"Gender set to **{selected_gender}**! Please select your pronouns:",
            view=PronounsSelectionView(user_id)
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in gender_callback for user {user_id}: {e}")

async def pronouns_callback(dropdown, interaction, user_id):
    """
    Callback for pronouns selection.
    """
    try:
        selected_pronouns = dropdown.values[0]
        character_creation_sessions[user_id]['pronouns'] = selected_pronouns
        logging.info(f"User {user_id} selected pronouns: {selected_pronouns}")

        # Proceed to description input using a modal
        await interaction.response.send_modal(DescriptionModal(user_id))
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in pronouns_callback for user {user_id}: {e}")

async def species_callback(dropdown, interaction, user_id):
    """
    Callback for species selection.
    """
    try:
        selected_species = dropdown.values[0]
        character_creation_sessions[user_id]['species'] = selected_species
        logging.info(f"User {user_id} selected species: {selected_species}")

        # Proceed to class selection
        await interaction.response.edit_message(
            content=f"Species set to **{selected_species}**! Please select a class:",
            view=ClassSelectionView(user_id)
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in species_callback for user {user_id}: {e}")

async def class_callback(dropdown, interaction, user_id):
    """
    Callback for class selection.
    """
    try:
        selected_class = dropdown.values[0]
        character_creation_sessions[user_id]['char_class'] = selected_class
        logging.info(f"User {user_id} selected class: {selected_class}")

        # Proceed to ability score assignment

        # Send the embed with the PhysicalAbilitiesView
        await interaction.response.edit_message(
            content="Let's begin your character creation!\n\n"
            f"You have **{POINT_BUY_TOTAL} points** to distribute among your abilities using the point-buy system.\n\n"
            "Here's how the costs work:\n"
            "- **8:** Gain 2 points\n"
            "- **9:** Gain 1 point\n"
            "- **10:** 0 points\n"
            "- **11:** Spend 1 point\n"
            "- **12:** Spend 2 points\n"
            "- **13:** Spend 3 points\n"
            "- **14:** Spend 5 points\n"
            "- **15:** Spend 7 points\n\n"
            "No ability score can be raised above **15**, and none can be lowered below **8**.\n\n"
            "Please assign your **Physical Attributes**:",
            view=PhysicalAbilitiesView(user_id)
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in class_callback for user {user_id}: {e}")

def generate_ability_embed(user_id):
    """
    Generates an embed reflecting the current ability scores and remaining points.
    """
    try:
        remaining_points = POINT_BUY_TOTAL - character_creation_sessions[user_id]['points_spent']
        assignments = character_creation_sessions[user_id]['stats']

        embed = discord.Embed(title="Character Creation - Ability Scores", color=discord.Color.blue())
        embed.add_field(name="Remaining Points", value=f"{remaining_points}/{POINT_BUY_TOTAL}", inline=False)

        # Add assigned scores
        for ability in ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma']:
            score = assignments.get(ability, 10)
            embed.add_field(name=ability, value=str(score), inline=True)

        embed.set_footer(text="Assign your ability scores using the dropdowns below.")

        return embed
    except Exception as e:
        logging.error(f"Error generating embed for user {user_id}: {e}")
        return None
    
# Character Creation Views
class CharacterCreationView(discord.ui.View):
    """
    Initial view for character creation with a start button.
    """
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.add_item(StartCharacterButton(bot))

class StartCharacterButton(discord.ui.Button):
    def __init__(self, bot):
        super().__init__(label="Start Character Creation", style=discord.ButtonStyle.green)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = str(interaction.user.id)

            # Initialize session
            character_creation_sessions[user_id] = {'stats': {}, 'points_spent': 0}

            # Create initial embed
            embed = Embed(title="Character Creation - Ability Scores", color=discord.Color.blue())
            embed.add_field(name="Remaining Points", value=f"{POINT_BUY_TOTAL}/{POINT_BUY_TOTAL}", inline=False)
            embed.set_footer(text="Assign your ability scores using the dropdowns below.")

            # Present the modal to get the character's name
            await interaction.response.send_modal(CharacterNameModal(user_id))
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {e}", ephemeral=True)
            logging.error(f"Error in StartCharacterButton callback for user {user_id}: {e}")


class CharacterNameModal(discord.ui.Modal):
    def __init__(self, user_id):
        super().__init__(title="Enter Character Name")
        self.user_id = user_id
        self.character_name = discord.ui.TextInput(label="Character Name")
        self.add_item(self.character_name)


    async def on_submit(self, interaction: discord.Interaction):
        character_name = self.children[0].value
        character_creation_sessions[self.user_id]['name'] = character_name
        logging.info(f"User {self.user_id} entered name: {character_name}")

        # Send or edit the message to proceed to gender selection
        await interaction.response.send_message(
            content="Character name set! Please select your gender:",
            view=GenderSelectionView(self.user_id),
            ephemeral=True
        )
        # Store the message object in the session for later editing
        character_creation_sessions[self.user_id]['message'] = await interaction.original_response()

class DescriptionModal(discord.ui.Modal):
    def __init__(self, user_id):
        super().__init__(title="Enter Character Description")
        self.user_id = user_id
        self.description = discord.ui.TextInput(
            label="Character Description",
            style=discord.TextStyle.long,
            max_length=1000  # Optional: Limit input length
        )
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        description = self.children[0].value
        word_count = len(description.split())
        if word_count > 200:
            await interaction.response.send_message(
                f"Description is too long ({word_count} words). Please limit it to 200 words.",
                ephemeral=True
            )
            # Re-show the modal for input
            await interaction.response.send_modal(DescriptionModal(self.user_id))
        else:
            character_creation_sessions[self.user_id]['description'] = description
            logging.info(f"User {self.user_id} provided description with {word_count} words.")

            # Proceed to species selection
            await interaction.response.edit_message(
                content="Description set! Please select a species:",
                view=SpeciesSelectionView(self.user_id)
            )

class GenderSelectionView(discord.ui.View):
    """
    View for gender selection using a dropdown.
    """
    def __init__(self, user_id):
        super().__init__()
        options = [
            discord.SelectOption(label="Male", description="Male gender"),
            discord.SelectOption(label="Female", description="Female gender"),
            discord.SelectOption(label="Non-binary", description="Non-binary gender"),
            discord.SelectOption(label="Other", description="Other or unspecified gender"),
        ]
        self.add_item(GenericDropdown(
            placeholder="Choose your character's gender...",
            options=options,
            callback_func=gender_callback,
            user_id=user_id
        ))

class PronounsSelectionView(discord.ui.View):
    """
    View for pronouns selection using a dropdown.
    """
    def __init__(self, user_id):
        super().__init__()
        options = [
            discord.SelectOption(label="He/Him", description="He/Him pronouns"),
            discord.SelectOption(label="She/Her", description="She/Her pronouns"),
            discord.SelectOption(label="They/Them", description="They/Them pronouns"),
            discord.SelectOption(label="Other", description="Other pronouns"),
        ]
        self.add_item(GenericDropdown(
            placeholder="Choose your character's pronouns...",
            options=options,
            callback_func=pronouns_callback,
            user_id=user_id
        ))

class SpeciesSelectionView(discord.ui.View):
    """
    View for species selection using a dropdown.
    """
    def __init__(self, user_id):
        super().__init__()
        options = [
            discord.SelectOption(label="Human", description="A versatile and adaptable species."),
            discord.SelectOption(label="Elf", description="Graceful and attuned to magic."),
            discord.SelectOption(label="Dwarf", description="Sturdy and resilient."),
            discord.SelectOption(label="Orc", description="Strong and fierce."),
            # Add more species as needed
        ]
        self.add_item(GenericDropdown(
            placeholder="Choose your species...",
            options=options,
            callback_func=species_callback,
            user_id=user_id
        ))

class ClassSelectionView(discord.ui.View):
    """
    View for class selection using a dropdown.
    """
    def __init__(self, user_id):
        super().__init__()
        options = [
            discord.SelectOption(label="Warrior", description="A strong fighter."),
            discord.SelectOption(label="Mage", description="A wielder of magic."),
            discord.SelectOption(label="Rogue", description="A stealthy character."),
            discord.SelectOption(label="Cleric", description="A healer and protector."),
            # Add more classes as needed
        ]
        self.add_item(GenericDropdown(
            placeholder="Choose your class...",
            options=options,
            callback_func=class_callback,
            user_id=user_id
        ))

async def update_embed(interaction, user_id):
    """
    Updates the embed in the original message to reflect the current state.
    """
    embed = generate_ability_embed(user_id)
    if embed:
        await interaction.message.edit(embed=embed)
        logging.info(f"Embed updated for user {user_id}.")
    else:
        logging.error(f"Failed to update embed for user {user_id}.")

class PhysicalAbilitiesView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.physical_abilities = ['Strength', 'Dexterity', 'Constitution']
        
        for ability in self.physical_abilities:
            current_score = character_creation_sessions[user_id]['stats'].get(ability, None)
            self.add_item(AbilitySelect(user_id, ability, current_score))
        self.add_item(NextMentalAbilitiesButton(user_id))
        logging.info(f"PhysicalAbilitiesView created for user {user_id} with {len(self.children)} components.")

class MentalAbilitiesView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.mental_abilities = ['Intelligence', 'Wisdom', 'Charisma']
        for ability in self.mental_abilities:
            current_score = character_creation_sessions[user_id]['stats'].get(ability, None)
            self.add_item(AbilitySelect(user_id, ability, current_score))
        self.add_item(BackPhysicalAbilitiesButton(user_id))
        self.add_item(FinishAssignmentButton(user_id))
        logging.info(f"MentalAbilitiesView created for user {user_id} with {len(self.children)} components.")

class AbilitySelect(discord.ui.Select):
    """
    Dropdown for selecting an ability score for a specific ability.
    """
    def __init__(self, user_id, ability_name, current_score=None):
        self.user_id = user_id
        self.ability_name = ability_name
        options = [
            discord.SelectOption(label="8", description="Gain 2 points", default=(current_score == 8)),
            discord.SelectOption(label="9", description="Gain 1 point", default=(current_score == 9)),
            discord.SelectOption(label="10", description="0 points", default=(current_score == 10)),
            discord.SelectOption(label="11", description="Spend 1 point", default=(current_score == 11)),
            discord.SelectOption(label="12", description="Spend 2 points", default=(current_score == 12)),
            discord.SelectOption(label="13", description="Spend 3 points", default=(current_score == 13)),
            discord.SelectOption(label="14", description="Spend 5 points", default=(current_score == 14)),
            discord.SelectOption(label="15", description="Spend 7 points", default=(current_score == 15)),
        ]
        # Set the placeholder to show the current score
        if current_score is not None:
            placeholder_text = f"{self.ability_name}: {current_score}"
        else:
            placeholder_text = f"Assign {ability_name} score..."
        super().__init__(
            placeholder=placeholder_text,
            min_values=1,
            max_values=1,
            options=options
        )
        logging.info(f"AbilitySelect initialized for {ability_name} with current_score={current_score}.")

    async def callback(self, interaction: discord.Interaction):
        """
        Callback for ability score selection.
        """
        try:
            selected_score = int(self.values[0])
            cost = calculate_score_cost(selected_score)
            user_id = self.user_id
            cur_view=self.view
            cur_message=interaction.message.content
            
            # Retrieve previous score and cost
            previous_score = character_creation_sessions[user_id]['stats'].get(self.ability_name, 10)
            previous_cost = calculate_score_cost(previous_score)

            # Update the session data
            character_creation_sessions[user_id]['stats'][self.ability_name] = selected_score
            character_creation_sessions[user_id]['points_spent'] += (cost - previous_cost)
            logging.info(f"User {user_id} set {self.ability_name} to {selected_score}. Cost: {cost}. Total points spent: {character_creation_sessions[user_id]['points_spent']}.")

            remaining_points = POINT_BUY_TOTAL - character_creation_sessions[user_id]['points_spent']

            if remaining_points < 0:
                # Revert the assignment
                character_creation_sessions[user_id]['stats'][self.ability_name] = previous_score
                character_creation_sessions[user_id]['points_spent'] -= (cost - previous_cost)
                await interaction.response.send_message(
                    f"Insufficient points to assign **{selected_score}** to **{self.ability_name}**. You have **{remaining_points + (cost - previous_cost)} points** remaining.",
                    ephemeral=True
                )
                logging.warning(f"User {user_id} overspent points while assigning {self.ability_name}.")
                return

            current_score=character_creation_sessions[user_id]['stats'].get(self.ability_name, 10),

            # Determine which view to recreate
            if isinstance(self.view, PhysicalAbilitiesView):
                new_view = PhysicalAbilitiesView(user_id)
            elif isinstance(self.view, MentalAbilitiesView):
                new_view = MentalAbilitiesView(user_id)
            else:
                # Fallback or error handling
                new_view = self.view
            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            # Update the message content, view, and embed
            await interaction.response.edit_message(
                view=new_view,
                embed=embed  
            )
        except ValueError:
            await interaction.followup.send_message(
                f"Invalid input for **{self.ability_name}**. Please select a valid score.",
                ephemeral=True
            )
            logging.error(f"User {self.user_id} selected an invalid score for {self.ability_name}: {self.values[0]}")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in AbilitySelect callback for {self.ability_name}, user {self.user_id}: {e}")


class NextMentalAbilitiesButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Next", style=discord.ButtonStyle.blurple)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id

            # Check if points_spent exceeds POINT_BUY_TOTAL
            points_spent = character_creation_sessions[user_id]['points_spent']
            if points_spent > POINT_BUY_TOTAL:
                await interaction.response.send_message(
                    f"You have overspent your points by **{points_spent - POINT_BUY_TOTAL}** points. Please adjust your ability scores.",
                    ephemeral=True
                )
                logging.warning(f"User {user_id} overspent points before navigating to MentalAbilitiesView.")
                return

            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            # Update the message content, view, and embed
            await interaction.response.edit_message(
                content="Now, please assign your mental abilities:",
                view=MentalAbilitiesView(user_id),
                embed=embed  
            )
            logging.info(f"User {user_id} navigated to MentalAbilitiesView.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in NextMentalAbilitiesButton callback for user {self.user_id}: {e}")


class BackPhysicalAbilitiesButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Back", style=discord.ButtonStyle.gray)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id

            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            # Proceed back to PhysicalAbilitiesView
            await interaction.response.edit_message(
                content="Returning to Physical Abilities assignment:",
                view=PhysicalAbilitiesView(user_id),
                embed=embed 
            )
            logging.info(f"User {user_id} navigated back to PhysicalAbilitiesView.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in BackPhysicalAbilitiesButton callback for user {self.user_id}: {e}")


class FinishAssignmentButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Finish", style=discord.ButtonStyle.green)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id
            allocation = character_creation_sessions[user_id]['stats']
            is_valid, message = is_valid_point_allocation(allocation)
            if not is_valid:
                await interaction.response.send_message(
                    f"Point allocation error: {message}. Please adjust your scores before finalizing.",
                    ephemeral=True
                )
                logging.warning(f"User {user_id} failed point allocation validation: {message}")
                return

            # Generate the updated embed
            embed = generate_ability_embed(user_id)

            await interaction.response.edit_message(
                content="All ability scores have been assigned correctly. Click the button below to finish.",
                view=FinalizeCharacterView(user_id),
                embed=embed 
            )
            logging.info(f"User {user_id} prepared to finalize character creation.")
        except KeyError:
            await interaction.response.send_message(
                "Character data not found. Please start the character creation process again.",
                ephemeral=True
            )
            logging.error(f"Character data not found for user {self.user_id} during finalization.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in FinishAssignmentButton callback for user {self.user_id}: {e}")


class FinalizeCharacterView(discord.ui.View):
    """
    View to finalize character creation.
    """
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.add_item(FinalizeCharacterButton(user_id))
        logging.info(f"FinalizeCharacterView created for user {user_id} with {len(self.children)} components.")

class FinalizeCharacterButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Finish Character Creation", style=discord.ButtonStyle.green)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id
            session = character_creation_sessions.get(user_id, {})

            if not session:
                await interaction.response.send_message("No character data found. Please start over.", ephemeral=True)
                logging.error(f"No character data found for user {user_id} during finalization.")
                return

            allocation = session.get('stats', {})
            is_valid, message = is_valid_point_allocation(allocation)
            if not is_valid:
                await interaction.response.send_message(f"Character creation failed: {message}", ephemeral=True)
                logging.warning(f"User {user_id} failed point allocation validation during finalization: {message}")
                return

            character = await finalize_character(interaction, user_id)
            if character:
                # Save the character data
                characters[user_id] = character
                save_characters(characters)
                del character_creation_sessions[user_id]
                logging.info(f"Character '{character.name}' created successfully for user {user_id}.")

                # Create a final character summary embed
                embed = discord.Embed(title=f"Character '{character.name}' Created!", color=discord.Color.green())
                embed.add_field(name="Species", value=character.species, inline=True)
                embed.add_field(name="Class", value=character.char_class, inline=True)
                embed.add_field(name="Gender", value=character.gender, inline=True)
                embed.add_field(name="Pronouns", value=character.pronouns, inline=True)
                embed.add_field(name="Description", value=character.description, inline=False)
                for stat, value in character.stats.items():
                    embed.add_field(name=stat, value=str(value), inline=True)

                # Confirm creation
                await interaction.response.edit_message(
                    content=f"Your character has been created successfully!",
                    view=None,
                    embed=embed
                )
            else:
                await interaction.response.send_message("Character creation failed. Please start over.", ephemeral=True)
                logging.error(f"Character creation failed for user {user_id}.")
        except KeyError:
            await interaction.response.send_message("Character data not found. Please start over.", ephemeral=True)
            logging.error(f"Character data not found for user {self.user_id} during finalization.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in FinalizeCharacterButton callback for user {self.user_id}: {e}")

async def finalize_character(interaction: discord.Interaction, user_id):
    """
    Finalizes the character creation by instantiating a Character object.
    Args:
        interaction (discord.Interaction): The interaction object.
        user_id (str): The user's ID.
    Returns:
        Character or None: The created Character object or None if failed.
    """
    session = character_creation_sessions.get(user_id, {})
    if not session:
        await interaction.response.send_message("No character data found.", ephemeral=True)
        logging.error(f"No session data found for user {user_id} during finalization.")
        return None

    allocation = session.get('stats', {})
    is_valid, message = is_valid_point_allocation(allocation)
    if not is_valid:
        await interaction.response.send_message(f"Character creation failed: {message}", ephemeral=True)
        logging.warning(f"User {user_id} failed point allocation validation: {message}")
        return None


    # Example area name to assign
    starting_area_name = "Clearing"

    # Retrieve the Area object
    starting_area = area_lookup.get(starting_area_name)

    if not starting_area:
        raise ValueError(f"Starting area '{starting_area_name}' does not exist in area_lookup.")


    # Create the Character instance
    character = Character(
        name=session.get('name', "Unnamed Character"),
        user_id=session.get('user_id', user_id),
        species=session.get('species', "Unknown Species"),
        char_class=session.get('char_class', "Unknown Class"),
        gender=session.get('gender', "Unspecified"),
        pronouns=session.get('pronouns', "They/Them"),
        description=session.get('description', "No description provided."),
        stats=session.get('stats', {
            'Strength': 10,
            'Dexterity': 10,
            'Constitution': 10,
            'Intelligence': 10,
            'Wisdom': 10,
            'Charisma': 10
        }),
        skills=session.get('skills', {}),
        inventory=session.get('inventory', {}),
        equipment=session.get('equipment', {}),
        currency=session.get('currency', {}),
        spells=session.get('spells', {}),
        abilities=session.get('abilities', {}),
        ac=session.get('ac', 10),
        spellslots=session.get('spellslots', {}),
        movement_speed=session.get('movement_speed', 30),
        travel_end_time=session.get('travel_end_time', None),
        level=session.get('level', 1),
        xp=session.get('xp', 0),
        reputation=session.get('reputation', 0),
        faction=session.get('faction', "Neutral"),
        relations=session.get('relations', {}),
        max_hp=session.get('max_hp', 1),
        curr_hp=session.get('curr_hp', 1),
        current_area = starting_area,
        current_location=session.get('current_location') if session.get('current_location') else "Unknown",
        current_region=session.get('current_region') if session.get('current_region') else "Avaloria",
        current_continent=session.get('current_continent') if session.get('current_continent') else "Eldoria",
        current_world=session.get('current_world') if session.get('current_world') else "Endara",
    )
    

    return character

# ---------------------------- #
#          Command Tree         #
# ---------------------------- #

@tree.command(name="create_character", description="Create a new character")
async def create_character(interaction: discord.Interaction):
    """
    Slash command to initiate character creation.
    """
    try:
        await interaction.user.send("Let's create your character!", view=CharacterCreationView(bot))
        await interaction.response.send_message("Check your DMs to start character creation!", ephemeral=True)
        logging.info(f"User {interaction.user.id} initiated character creation.")
    except discord.Forbidden:
        await interaction.response.send_message(
            "Unable to send you a DM. Please check your privacy settings.",
            ephemeral=True
        )
        logging.warning(f"Could not send DM to user {interaction.user.id} for character creation.")
    except Exception as e:
        await interaction.response.send_message(
            "An unexpected error occurred. Please try again later.",
            ephemeral=True
        )
        logging.error(f"Error in create_character command for user {interaction.user.id}: {e}")

@tree.command(name="attack", description="Attack an NPC in your current area.")
@app_commands.describe(npc_name="The name of the NPC to attack.")
async def attack(interaction: discord.Interaction, npc_name: str):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    area = character.current_area
    for npc in area.npcs:
        if npc.name.lower() == npc_name.lower():
            # Implement combat logic here
            # For simplicity, we'll assume the NPC is defeated
            area.remove_npc(npc.name)
            # Optionally, transfer NPC's inventory to the area or player
            area.inventory.extend(npc.inventory)
            await interaction.response.send_message(f"You have defeated **{npc.name}**!", ephemeral=False)
            return

    await interaction.response.send_message(f"**{npc_name}** is not in **{area.name}**.", ephemeral=True)

@tree.command(name="npc_list", description="List all NPCs in your current area.")
async def npc_list(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    area = character.current_area
    if area.npcs:
        npc_names = ', '.join(npc.name for npc in area.npcs)
        await interaction.response.send_message(f"NPCs in **{area.name}**: {npc_names}", ephemeral=False)
    else:
        await interaction.response.send_message(f"There are no NPCs in **{area.name}**.", ephemeral=False)

@tree.command(name="talk", description="Talk to an NPC in your current area.")
@app_commands.describe(npc_name="The name of the NPC to talk to.")
async def talk(interaction: discord.Interaction, npc_name: str):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    area = character.current_area
    for npc in area.npcs:
        if npc.name.lower() == npc_name.lower():
            # For simplicity, send the first dialogue line
            dialogue = npc.get_dialogue if npc.dialogue else f"{npc.name} has nothing to say."
            await interaction.response.send_message(f"**{npc.name}** says: \"{dialogue}\"", ephemeral=False)
            return

    await interaction.response.send_message(f"**{npc_name}** is not in **{area.name}**.", ephemeral=True)


@tree.command(name='inventory', description="View your character's inventory.")
async def inventory_command(ctx):
    user_id = str(ctx.user.id)
    character = characters.get(user_id)
    if character:
        inventory_list = '\n'.join(f"- {item.name} ({item.item_type})" for item in character.inventory)
        if not inventory_list:
            inventory_list = "Your inventory is empty."
        await ctx.response.send_message(f"**{character.name}'s Inventory:**\n{inventory_list}")
    else:
        await ctx.response.send_message("You don't have a character yet. Use `/create_character` to get started.")

@tree.command(name="pickup", description="Pick up an item from the area.")
@app_commands.describe(item_name="The name of the item to pick up.")
async def pickup(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    channel_id = str(interaction.channel_id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet. Use `/create_character` to get started.", ephemeral=True)
        return

    area_inventory = get_area_inventory(channel_id)
    # Find the item in the area inventory
    for item in area_inventory:
        if item.name.lower() == item_name.lower():
            # Check if character can carry the item
            if character.can_carry_more(item.weight):
                character.add_item_to_inventory(item)
                area_inventory.remove(item)
                save_characters(characters)
                await interaction.response.send_message(f"You picked up **{item.name}**.", ephemeral=False)
                return
            else:
                await interaction.response.send_message("You can't carry any more weight.", ephemeral=True)
                return

    await interaction.response.send_message(f"The item **{item_name}** is not available in this area.", ephemeral=True)

@tree.command(name="drop", description="Drop an item from your inventory into the area.")
@app_commands.describe(item_name="The name of the item to drop.")
async def drop(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    channel_id = str(interaction.channel_id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    # Find the item in the character's inventory
    for item in character.inventory:
        if item.name.lower() == item_name.lower():
            character.remove_item_from_inventory(item.name)
            area_inventory = get_area_inventory(channel_id)
            area_inventory.append(item)
            save_characters(characters)
            await interaction.response.send_message(f"You dropped **{item.name}** into the area.", ephemeral=False)
            return

    await interaction.response.send_message(f"You don't have an item named **{item_name}** in your inventory.", ephemeral=True)

@tree.command(name="destroy", description="Destroy an item in your inventory.")
@app_commands.describe(item_name="The name of the item to destroy.")
async def destroy(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    # Find the item in the character's inventory
    for item in character.inventory:
        if item.name.lower() == item_name.lower():
            character.remove_item_from_inventory(item.name)
            save_characters(characters)
            await interaction.response.send_message(f"You have destroyed **{item.name}**.", ephemeral=False)
            return

    await interaction.response.send_message(f"You don't have an item named **{item_name}**.", ephemeral=True)

@tree.command(name="equip", description="Equip an item from your inventory.")
@app_commands.describe(item_name="The name of the item to equip.", slot="The equipment slot.")
async def equip(interaction: discord.Interaction, item_name: str, slot: str):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    slot = slot.lower()
    valid_slots = ['armor', 'left_hand', 'right_hand', 'back'] + [f'belt_slot_{i+1}' for i in range(4)] + [f'magic_slot_{i+1}' for i in range(3)]

    if slot not in valid_slots:
        await interaction.response.send_message(f"Invalid slot. Valid slots are: {', '.join(valid_slots)}", ephemeral=True)
        return

    # Find the item in the character's inventory
    for item in character.inventory:
        if item.name.lower() == item_name.lower():
            try:
                character.equip_item(item, slot)
                save_characters(characters)
                await interaction.response.send_message(f"You have equipped **{item.name}** to **{slot}**.", ephemeral=False)
                return
            except ValueError as e:
                await interaction.response.send_message(str(e), ephemeral=True)
                return

    await interaction.response.send_message(f"You don't have an item named **{item_name}** in your inventory.", ephemeral=True)

@tree.command(name="unequip", description="Unequip an item from a slot back to your inventory.")
@app_commands.describe(slot="The equipment slot to unequip.")
async def unequip(interaction: discord.Interaction, slot: str):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    slot = slot.lower()
    valid_slots = ['armor', 'left_hand', 'right_hand', 'back'] + [f'belt_slot_{i+1}' for i in range(4)] + [f'magic_slot_{i+1}' for i in range(3)]

    if slot not in valid_slots:
        await interaction.response.send_message(f"Invalid slot. Valid slots are: {', '.join(valid_slots)}", ephemeral=True)
        return

    try:
        character.unequip_item(slot)
        save_characters(characters)
        await interaction.response.send_message(f"You have unequipped the item from **{slot}**.", ephemeral=False)
    except ValueError as e:
        await interaction.response.send_message(str(e), ephemeral=True)

@tree.command(name="use", description="Use a consumable item from your inventory.")
@app_commands.describe(item_name="The name of the item to use.")
async def use_item(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    # Find the item in the character's inventory
    for item in character.inventory:
        if item.name.lower() == item_name.lower():
            if item.item_type.lower() == 'consumable':
                # Apply the item's effect
                result = character.use_consumable(item)
                save_characters(characters)
                await interaction.response.send_message(f"You used **{item.name}**. {result}", ephemeral=False)
                return
            else:
                await interaction.response.send_message(f"**{item.name}** is not a consumable item.", ephemeral=True)
                return

    await interaction.response.send_message(f"You don't have an item named **{item_name}**.", ephemeral=True)

@tree.command(name="examine", description="Examine an item in your inventory or equipment.")
@app_commands.describe(item_name="The name of the item to examine.")
async def examine(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    # Search in inventory
    for item in character.inventory:
        if item.name.lower() == item_name.lower():
            await interaction.response.send_message(f"**{item.name}**: {item.description}", ephemeral=True)
            return

    # Search in equipment
    for slot, equipped_item in character.equipment.items():
        if isinstance(equipped_item, list):  # For slots like 'belt_slots' or 'magic_slots'
            for sub_item in equipped_item:
                if sub_item and sub_item.name.lower() == item_name.lower():
                    await interaction.response.send_message(f"**{sub_item.name}**: {sub_item.description}", ephemeral=True)
                    return
        elif equipped_item and equipped_item.name.lower() == item_name.lower():
            await interaction.response.send_message(f"**{equipped_item.name}**: {equipped_item.description}", ephemeral=True)
            return

    await interaction.response.send_message(f"You don't have an item named **{item_name}** in your inventory or equipment.", ephemeral=True)

@tree.command(name="identify", description="Identify a magical item in your inventory.")
@app_commands.describe(item_name="The name of the item to identify.")
async def identify(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    # Find the item in the character's inventory
    for item in character.inventory:
        if item.name.lower() == item_name.lower():
            if item.is_magical:
                # Assume an Arcana check is needed
                stat = 'Intelligence'
                roll, total = perform_ability_check(character, stat)
                # Set a DC for identifying magical items
                dc = 15  # You can adjust this value
                if total >= dc:
                    # Reveal magical properties
                    item_description = item.description + "\nMagical Properties: " + str(item.effect)
                    await interaction.response.send_message(f"**{item.name}** identified!\n{item_description}", ephemeral=False)
                else:
                    await interaction.response.send_message(f"You failed to identify **{item.name}**.", ephemeral=True)
                return
            else:
                await interaction.response.send_message(f"**{item.name}** is not a magical item.", ephemeral=True)
                return

    await interaction.response.send_message(f"You don't have an item named **{item_name}**.", ephemeral=True)

@tree.command(name="travel", description="Move to a connected area.")
@app_commands.describe(destination="The name of the area to move to.")
async def travel(interaction: discord.Interaction, destination: str):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    current_area = character.current_area
    if not current_area:
        await interaction.response.send_message("Your current area is undefined.", ephemeral=True)
        return

    # Find the area with the given name in connected areas
    target_area = None
    for area in current_area.connected_areas:
        if area.name.lower() == destination.lower():
            target_area = area
            break

    if not target_area:
        await interaction.response.send_message(f"**{destination}** is not connected to your current area.", ephemeral=True)
        return

    travel_time = get_travel_time(character, target_area)  # Implement this function accordingly

    # For testing, ensure travel_time is at least 5 seconds
    travel_time = max(travel_time, 5)

    character.is_traveling = True
    character.travel_destination = target_area
    character.travel_end_time = datetime.utcnow().timestamp() + travel_time

    # Update the characters dictionary
    characters[user_id] = character

    # Save characters
    save_characters(characters)

    # Send traveling message
    await interaction.response.send_message(
        f"You begin traveling to **{target_area.name}**. It will take approximately {travel_time / 60:.2f} minutes.",
        ephemeral=False
    )

    # Start the travel_task
    asyncio.create_task(travel_task(character, user_id, characters, save_characters))

# Implement the autocomplete callback
@travel.autocomplete('destination')
async def travel_autocomplete(interaction: discord.Interaction, current: str):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        return []  # No suggestions if user has no character

    current_area = character.current_area
    if not current_area:
        return []  # No suggestions if current area is undefined

    # Fetch connected areas
    connected_areas = current_area.connected_areas

    # Filter based on the current input (case-insensitive)
    suggestions = [
        app_commands.Choice(name=area.name, value=area.name)
        for area in connected_areas
        if current.lower() in area.name.lower()
    ]

    # Discord limits to 25 choices
    return suggestions[:25]


@tree.command(name="travel_location", description="Travel to a different location within your current region.")
@app_commands.describe(location_name="The name of the location to travel to.")
async def travel_location(interaction: discord.Interaction, location_name: str):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)
    
    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return
    
    # Find the location in the current region
    for location in character.current_region.locations:
        if location.name.lower() == location_name.lower():
            if character.move_to_location(location):
                save_characters(characters)
                await interaction.response.send_message(f"You have moved to **{location.name}**.", ephemeral=False)
                return
            else:
                await interaction.response.send_message(f"You cannot move to **{location.name}**.", ephemeral=True)
                return
    
    await interaction.response.send_message(f"Location **{location_name}** not found in your current region.", ephemeral=True)


@tree.command(name="rest", description="Rest to regain health and spell slots.")
async def rest(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    character.rest()
    save_characters(characters)
    await interaction.response.send_message("You have rested and regained health and spell slots.", ephemeral=False)

@tree.command(name="location", description="View your current location.")
async def location(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    area = character.current_area
    location = character.current_location
    region = character.current_region
    continent = character.current_continent
    world = character.current_world

    # Ensure 'area' is an Area object
    if area and not isinstance(area, Area):
        logging.error(f"current_area for user '{user_id}' is not an Area object.")
        await interaction.response.send_message("Your character's area data is corrupted.", ephemeral=True)
        return

    # Construct the response message
    response_message = (
        f"You are in **{area.name}**, located in **{location}**, "
        f"**{region}**, **{continent}**, **{world}**."
    )

    await interaction.response.send_message(
        response_message,
        ephemeral=False
    )

@tree.command(name="scene", description="View the description of your current area.")
async def scene(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )
        return

    area = character.current_area
    if not area:
        await interaction.response.send_message(
            "Your current area could not be found. Please contact the administrator.",
            ephemeral=True
        )
        return

    # Create an embed
    embed = discord.Embed(title=area.name, description=area.description, color=0x00ff00)

    # Connected Areas
    if area.connected_areas:
        connected_area_names = ', '.join(connected_area.name for connected_area in area.connected_areas)
        embed.add_field(name="Connected Areas", value=connected_area_names, inline=False)
    else:
        embed.add_field(name="Connected Areas", value="None", inline=False)

    # NPCs
    if area.npcs:
        npc_names = ', '.join(npc.name for npc in area.npcs)
        embed.add_field(name="NPCs Present", value=npc_names, inline=False)
    else:
        embed.add_field(name="NPCs Present", value="None", inline=False)

    # Items
    if area.inventory:
        item_names = ', '.join(item.name for item in area.inventory)
        embed.add_field(name="Items Available", value=item_names, inline=False)
    else:
        embed.add_field(name="Items Available", value="None", inline=False)

    # Send the embed
    await interaction.response.send_message(embed=embed, ephemeral=False)

@tree.command(name="stats", description="View your character's stats.")
async def stats(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    character = characters.get(user_id)

    if not character:
        await interaction.response.send_message("You don't have a character yet.", ephemeral=True)
        return

    stats_str = '\n'.join(f"{stat}: {value}" for stat, value in character.stats.items())
    await interaction.response.send_message(f"**{character.name}'s Stats:**\n{stats_str}", ephemeral=False)


# ---------------------------- #
#           Events              #
# ---------------------------- #

@bot.event
async def on_ready():
    """
    Event handler for when the bot is ready.
    """
    try:
        print(f'Logged in as {bot.user.name}')
        await tree.sync()
        print("Command tree synchronized.")
        logging.info("Bot is ready and command tree synchronized.")
    except Exception as e:
        print(f"An error occurred in on_ready: {e}")
        logging.error(f"Error in on_ready event: {e}")

@bot.event
async def on_message(message: discord.Message):
    """
    Event handler for processing messages to handle in-game actions.
    """
    if message.author == bot.user:
        return

    logging.info(f"on_message triggered for message from {message.author.id}: '{message.content}'")

    # Check for '?listactions' command
    if message.content.strip() == '?listactions':
        if actions:
            action_list = ', '.join(actions.keys())
            await message.channel.send(f"Recognized actions: {action_list}")
            logging.info(f"User {message.author.id} requested action list.")
        else:
            await message.channel.send("No actions are currently recognized.")
            logging.info(f"User {message.author.id} requested action list, but no actions are loaded.")
        return  # Early return to prevent further processing

    user_id = str(message.author.id)

    if user_id not in characters:
        characters[user_id] = Character(name=message.author.name)
        save_characters(characters)
        await message.channel.send(f'Character created for {message.author.name}.')
        logging.info(f"Character created for user {user_id} with name {message.author.name}.")

    character = characters[user_id]
    action, stat = await parse_action(message)
    if action and stat:
        logging.info(f"Processing action '{action}' for user {user_id} associated with stat '{stat}'.")
        roll, total = perform_ability_check(character, stat)
        if roll is None or total is None:
            logging.error(f"Ability check failed for user {user_id}.")
            return  # Ability check failed due to an error

        # Fetch the last 10 messages from the channel, excluding action commands
        channel_history = [msg async for msg in message.channel.history(limit=10) if not msg.content.startswith('?')]
        
        # Get the content of the last 5 non-action messages
        last_messages_content = [msg.content for msg in channel_history[:5]]

        # Construct the prompt for difficulty determination
        difficulty_prompt = (
            f"Player {character.name} attempts to {action}. "
            f"Keeping in mind that player characters are meant to be a cut above the average person in ability and luck, \n"
            f"based on the context of the action and the surrounding \n"
            f"circumstances contained in previous messages, talk yourself through the nuances of the \n"
            f"scene, the action, and what else is happening around them, and determine the difficulty (DC) of the task. "
            f"This should be represented with a number between 5 and 30, \n"
            f"with 5 being trivial (something like climbing a tree to escape a pursuing creature), 10 being very easy (something like recalling what you know about defeating an enemy), 12 being easy (something like tossing a rock at a close target), "
            f"15 being challenging (actions like identifying rare mushrooms and their unique properties), 17 being difficult (actions like breaking down a heavy wooden door), 20 being extremely \n"
            f"difficult (something like using rope to grapple onto an object while falling). \n"
            f"Above 20 should be reserved for actions that are increasingly \n"
            f"impossible. For example, 25 might be something like interpreting words in a language you don't understand \n"
            f"No difficulty should ever go above 30, which should be reserved \n"
            f"for actions that are almost certainly impossible, but a freak \n"
            f"chance of luck exists, something like convincing the main villain to abandon their plan and be their friend.\n"
            f"Just provide the number."
        )

        logging.info("Calling get_chatgpt_response for difficulty determination.")
        difficulty_response = await get_chatgpt_response(
            difficulty_prompt,
            last_messages_content,
            stat,
            total,
            roll,
            character,
            include_roll_info=False
        )
        logging.info("Completed get_chatgpt_response for difficulty determination.")

        try:
            difficulty = int(re.search(r'\d+', difficulty_response).group())
            logging.info(f"Difficulty determined for user {user_id}: {difficulty}")
        except (AttributeError, ValueError):
            COOLDOWN_PERIOD = 5  # Cooldown period in seconds
            current_time = asyncio.get_event_loop().time()
            if last_error_time.get(user_id, 0) is None or current_time - last_error_time.get(user_id, 0) > COOLDOWN_PERIOD:
                await message.channel.send("Sorry, I couldn't determine the difficulty of the task.")
                last_error_time[user_id] = current_time
                logging.error(f"Failed to parse difficulty for user {user_id}.")
            return

        # Determine the result based on the difficulty
        if roll == 20:
            result = "succeed with a critical success, obtaining an unexpected advantage or extraordinary result."
        elif total > difficulty:
            result = "succeed."
        elif total == difficulty:
            result = "succeed, but with a complication that heightens the tension."
        else:
            result = "fail."

        logging.info(f"Player {character.name} (user {user_id}) attempted to {action}. The DC was {difficulty}. It was a {result}.")

        # Construct the final prompt for narrative description
        prompt = (
            f"{character.name} attempted to {action} and they {result}.\n"
            f"Their gender is {character.gender} and their pronouns are {character.pronouns}.\n"
            f"Their species is: {character.species}\nA brief description of their character: {character.description}.\n"
            f"As the game master, describe their action and how the narrative and scene and NPCs react to this action. \n"
            f"Always end with 'What do you do? The DC was: {difficulty}.' \n" 
            f"And a brief explanation on the reasoning behind that number as DC. \n"
            f"Limit responses to 100 words.\n"
        )

        logging.info("Calling get_chatgpt_response for narrative response.")
        response = await get_chatgpt_response(
           prompt,
           last_messages_content,
           stat,
           total,
           roll,
           character,
           include_roll_info=True
        )
        logging.info("Completed get_chatgpt_response for narrative response.")

        logging.info(f"Sending narrative response to channel: {response}")
        await message.channel.send(response)
        logging.info(f"Narrative response sent to user {user_id}.")
        # Uncomment and implement update_world_anvil if needed
        # await update_world_anvil(character, action, response)
    else:
        # Optionally, do not send any message if no action is recognized
        logging.info("No valid action found in the message.")
        pass

    await bot.process_commands(message)

# ---------------------------- #
#          Helper Functions     #
# ---------------------------- #

def perform_ability_check(character, stat):
    """
    Performs an ability check by rolling a die and adding the stat modifier.
    Args:
        character (Character): The character performing the check.
        stat (str): The ability stat being checked.
    Returns:
        tuple: (roll, total) or (None, None) if failed.
    """
    try:
        modifier = character.get_stat_modifier(stat)
        roll = random.randint(1, 20)
        total = roll + modifier
        logging.info(f"Ability check for {character.name}: Rolled {roll} + modifier {modifier} = {total}")
        return roll, total
    except Exception as e:
        logging.error(f"Error in perform_ability_check for {character.name}: {e}")
        return None, None

async def parse_action(message):
    """
    Parses the user's message to identify actions prefixed with '?' and returns the action and associated stat.
    Args:
        message (discord.Message): The message object.
    Returns:
        tuple: (action, stat) or (None, None)
    """
    message_content = message.content.lower()
    logging.info(f"Parsing message from user {message.author.id}: '{message_content}'")

    # Updated regex pattern with negative lookbehind and lookahead
    pattern = r'(?<!\w)\?[A-Za-z]+(?!\w)'
    matches = re.findall(pattern, message_content)
    logging.info(f"Regex matches found: {matches}")

    # Track if multiple actions are found
    if len(matches) > 1:
        logging.warning(f"Multiple actions detected in message: {matches}")
        await message.channel.send("Please specify only one action at a time.")
        return None, None

    for match in matches:
        action = match.lstrip('?')
        logging.info(f"Parsed action: '{action}'")
        if action in actions:
            logging.info(f"Action recognized: '{action}'")
            return action, actions[action]
        else:
            await show_actions(message)
            logging.info(f"Action '{action}' not recognized.")
    
    logging.info("No valid action recognized in the message.")
    return None, None 

async def show_actions(message):
    """
    Sends a message listing recognized actions.
    Args:
        message (discord.Message): The message object.
    """
    if actions:
        action_list = ', '.join(actions.keys())
        await message.channel.send(f"Sorry, I don't recognize that action. Recognized actions: {action_list}")
        logging.info(f"Sent recognized actions list to user {message.author.id}.")
    else:
        await message.channel.send("No actions are currently recognized.")
        logging.info(f"User {message.author.id} requested actions, but no actions are loaded.")

async def get_chatgpt_response(prompt: str, channel_messages: list, stat: str, total: int, roll: int, character: Character, include_roll_info: bool = True) -> str:
    """
    Sends a prompt to OpenAI's GPT-4 using the AsyncOpenAI client and returns the response.
    Args:
        prompt (str): The prompt to send.
        channel_messages (list): The list of recent channel messages.
        stat (str): The ability stat involved in the check.
        total (int): The total check result.
        roll (int): The die roll result.
        character (Character): The character performing the action.
        include_roll_info (bool): Whether to include roll information in the response.
    Returns:
        str: The response from GPT-4.
    """
    try:
        # Prepare the messages for OpenAI
        messages = [
            {"role": "system", "content": "You are a game master for a fantasy role-playing game. Your job is to narrate the settings the players journey through, the results of their actions, and provide a sense of atmosphere through vivid and engaging descriptions."}
        ]

        # Add the last channel messages in chronological order
        for msg_content in reversed(channel_messages):
            messages.append({"role": "user", "content": msg_content})

        messages.append({"role": "user", "content": prompt})

        # Perform the asynchronous API call using the new method
        completion = await openai_client.chat.completions.create(
            model='gpt-4',
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )

        if include_roll_info:
            message_content = f"*{character.name}, your {stat} check result is {total} (rolled {roll} + modifier {character.get_stat_modifier(stat)}).* \n\n{completion.choices[0].message.content.strip()}"
        else:
            message_content = completion.choices[0].message.content.strip()
        return message_content
    except Exception as e:
        logging.error(f"Error in get_chatgpt_response: {e}")
        return "Sorry, I couldn't process that request."

# ---------------------------- #
#         Running the Bot      #
# ---------------------------- #

bot.run(DISCORD_BOT_TOKEN)
