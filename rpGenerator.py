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
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


# Initialize global variables
# Load environment variables from .env file
load_dotenv()

# Discord and OpenAI API keys
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

DISCORD_APP_ID = os.getenv('DISCORD_APP_ID')

# Global configuration
GUILD_CONFIGS = {
    1183315621690224640: {  # Guild ID
        'channels': {
            'game': 1183315622558433342,  # Main game channel
             # Optional additional channels
        },
        'starting_area': "Marketplace Square",
        'command_prefix': '/',  # Optional: per-guild prefix
        # Add any other guild-specific settings
    },
    817119234454192179: {  # Guild ID
        'channels': {
            'game': 1012729890287652886,  # Main game channel
             # Optional additional channels
        },
        'starting_area': "Marketplace Square",
        'command_prefix': '/',  # Optional: per-guild prefix
        # Add any other guild-specific settings
    },
    # Add more guilds as needed
}

ACTIONS_FILE = 'actions.json'
CHARACTERS_FILE = 'characters.json'
ITEMS_FILE = 'items.json'
NPCS_FILE = 'npcs.json'
AREAS_FILE = 'areas.json'
LOCATIONS_FILE = 'locations.json'
REGIONS_FILE = 'regions.json'
CONTINENTS_FILE = 'continents.json'
WORLD_FILE = 'world.json'

DEFAULT_STARTING_AREA = "Marketplace Square"

if 'character_creation_sessions' not in globals():
    character_creation_sessions = {} # List of CharacterCreationSession instances
if 'last_error_time' not in globals():
    last_error_time = None  # For global cooldowns per user
if 'global_cooldown' not in globals():
    global_cooldown = 5  # Global cooldown in seconds
if 'characters' not in globals():
    characters = None  # Dictionary to store Character instances
if 'game_data' not in globals():
    game_data = None
if 'area_lookup' not in globals():
    area_lookup = None
if 'items' not in globals():
    items = None
if 'npcs' not in globals():
    npcs = None
if 'actions' not in globals():
    actions = None
if 'channel_areas' not in globals():
    channel_areas = None  # Dictionary mapping channel IDs to Area instances
if 'character_cache' not in globals():
    character_cache = {}
    last_cache_update = 0
    CACHE_DURATION = 300  # 5 minutes in seconds



# ---------------------------- #
#        Configuration         #
# ---------------------------- #

def validate_json(filename):
    try:
        with open(filename, 'r') as f:
            json.load(f)
        print(f"{filename} is valid JSON.")
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in {filename}: {e}")
    except FileNotFoundError:
        print(f"{filename} not found.")
        return False
    return True

validate_json(WORLD_FILE)
validate_json(CONTINENTS_FILE)
validate_json(REGIONS_FILE)
validate_json(LOCATIONS_FILE)
validate_json(AREAS_FILE)
validate_json(ITEMS_FILE)
validate_json(NPCS_FILE)
validate_json(ACTIONS_FILE)
validate_json(CHARACTERS_FILE)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d:%(funcName)s - %(message)s',
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
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)
tree = bot.tree

scheduler = AsyncIOScheduler()


# ----------------------------
#        Game Data Loading
# ----------------------------

def load_world(filename=WORLD_FILE):
    with open(filename, 'r') as f:
        data = json.load(f)
    world = World.from_dict(data)
    return world

# Define load_items
def load_items(filename=ITEMS_FILE):
    """
    Load items from a JSON file.
    Args:
        filename (str): Path to the items JSON file
    Returns:
        dict: Dictionary mapping item names to Item instances
    """
    try:
        logging.info(f"Loading items from {filename}")
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not isinstance(data, dict):
            raise ValueError("Invalid items file format. Expected a dictionary.")
            
        item_lookup = {}
        for item_name, item_data in data.items():
            try:
                if not isinstance(item_data, dict):
                    logging.error(f"Invalid data format for item {item_name}")
                    continue
                    
                item = Item.from_dict(item_data)
                item_lookup[item_name] = item
                logging.debug(f"Successfully loaded item: {item_name}")
                
            except Exception as e:
                logging.error(f"Error loading item '{item.Name}': {e}")
                continue
                
        logging.info(f"Successfully loaded {len(item_lookup)} items")
        return item_lookup
        
    except Exception as e:
        logging.error(f"Unexpected error loading items: {e}")
        return {}


def load_npcs(item_lookup, filename=NPCS_FILE):
    """
    Load NPCs from location-specific JSON files.
    Args:
        item_lookup (dict): Dictionary of available items
        location_name (str): Name of the location to load NPCs from
    Returns:
        dict: Dictionary of NPCs for that location
    """
    try:
        npc_lookup = {}
        # Convert location name to lowercase and replace spaces with hyphens
        filename = filename
        logging.info(f"Loading NPCs from {filename}")

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for npc_name, npc_data in data.items():
                try:
                    npc = NPC.from_dict(npc_data, item_lookup)
                    npc_lookup[npc_name] = npc
                    logging.debug(f"Successfully loaded NPC: {npc_name}")
                except Exception as e:
                    logging.error(f"Error loading NPC '{npc_data.get('Name', 'Unknown')}': {e}")
            
            logging.info(f"Successfully loaded {len(npc_lookup)} NPCs from {filename}")
        
        except FileNotFoundError:
            logging.warning(f"No NPC file found for location: {filename}")
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {filename}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error loading NPCs from {filename}: {e}")
    except Exception as e:
        logging.error(f"Error in load_npcs: {e}")
        return {}
    
    return npc_lookup

def load_areas(item_lookup, filename=AREAS_FILE):
    try:
        with open(filename, 'r') as f:
            area_data = json.load(f)
            
        logging.debug(f"Raw area data keys: {list(area_data.keys())}")
        area_lookup = {}
        
        for area_key, data in area_data.items():
            try:
                logging.debug(f"Processing area: {area_key}")
                area = Area.from_dict(data, item_lookup)
                area_lookup[area_key] = area
                logging.debug(f"Successfully added area: {area_key}")
            except Exception as e:
                logging.error(f"Error processing area {area_key}: {e}")
                continue
        
        logging.info(f"Successfully loaded {len(area_lookup)} areas")
        return area_lookup
        
    except Exception as e:
        logging.error(f"Error loading areas from {filename}: {e}")
        return {}
    
def load_characters(filename=CHARACTERS_FILE, area_lookup=None):
    """
    Loads character data from the characters.json file.
    """
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        characters = {}
        for user_id, char_data in data.items():
            try:
                # Make sure to pass both the class and user_id
                character = Character.from_dict(
                    data=char_data,
                    user_id=user_id,
                    area_lookup=area_lookup,
                    item_lookup=items
                )
                if character:
                    characters[user_id] = character
                    logging.debug(f"Loaded character for user ID '{user_id}'.")
            except Exception as e:
                logging.error(f"Error loading character for user {user_id}: {e}")
                continue
        logging.info(f"Successfully loaded {len(characters)} characters from '{filename}'.")
        return characters
    except FileNotFoundError:
        logging.error(f"Characters file '{filename}' not found.")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from '{filename}': {e}")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error loading characters from '{filename}': {e}")
        return {}

def load_game_data():
    """
    Load all game data and return it in a dictionary.
    Returns:
        dict: Dictionary containing all game data
    """
    try:
        logging.info("Starting to load game data...")
        
        # Load items first
        item_lookup = load_items(ITEMS_FILE)
        if not item_lookup:
            logging.error("Failed to load items")
            return {}
        logging.info(f"Loaded {len(item_lookup)} items")

        # Load areas using the item lookup
        area_lookup = load_areas(item_lookup, AREAS_FILE)
        if not area_lookup:
            logging.error("Failed to load areas")
            return {}
        logging.info(f"Loaded {len(area_lookup)} areas")

        # Load NPCs using the item lookup
        npc_lookup = load_npcs(item_lookup, NPCS_FILE)
        if not npc_lookup:
            logging.error("Failed to load NPCs")
            return {}
        logging.info(f"Loaded {len(npc_lookup)} NPCs")

        # Load actions
        action_lookup = load_actions()
        if not action_lookup:
            logging.error("Failed to load actions")
            return {}
        logging.info(f"Loaded {len(action_lookup)} actions")

        # Resolve area connections and NPCs
        if not resolve_area_connections_and_npcs(area_lookup, npc_lookup):
            logging.error("Failed to resolve area connections and NPCs")
            return {}

        # Load characters
        character_lookup = load_characters(filename=CHARACTERS_FILE, area_lookup=area_lookup)


        # Return all lookups
        game_data = {
            'items': item_lookup,
            'areas': area_lookup,
            'npcs': npc_lookup,
            'actions': action_lookup,
            'characters': character_lookup
        }
        
        logging.debug(f"Game data loaded with keys: {game_data.keys()}")
        logging.debug(f"Area lookup contains {len(area_lookup)} areas: {list(area_lookup.keys())}")
        
        return game_data

    except Exception as e:
        logging.error(f"Error in load_game_data: {e}")
        return {}

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

# ---------------------------- #
#          Utilities           #
# ---------------------------- #

def verify_guild_configs():
    """
    Verify that all configured guilds are valid and accessible
    """
    for guild_id, config in GUILD_CONFIGS.items():
        guild = bot.get_guild(guild_id)
        if not guild:
            logging.warning(f"Could not find guild {guild_id}")
            continue
            
        # Verify channels
        for channel_type, channel_id in config['channels'].items():
            channel = bot.get_channel(channel_id)
            if not channel:
                logging.warning(f"Could not find {channel_type} channel {channel_id} in guild {guild_id}")
                continue
                
            # Verify permissions
            permissions = channel.permissions_for(guild.me)
            if not permissions.send_messages:
                logging.warning(f"Missing send messages permission in channel {channel_id} ({channel_type}) in guild {guild_id}")

def debug_cache_state():
    """Debug helper to examine current cache state"""
    logging.info("=== Cache Debug Information ===")
    logging.info(f"Cache exists: {character_cache is not None}")
    if character_cache is not None:
        logging.info(f"Cache size: {len(character_cache)}")
        logging.info(f"Cache keys: {list(character_cache.keys())}")
        for k, v in character_cache.items():
            logging.info(f"Cache entry: {k!r} -> {type(v).__name__}")
    logging.info("===========================")

def clean_user_id(user_id: str) -> str:
    """
    Cleans a user ID string to ensure consistent format.
    Removes brackets, quotes, and whitespace.
    """
    if user_id is None:
        return ""
    
    # Convert to string if not already
    user_id = str(user_id)
    
    # Fix the escape sequence - use a set of characters instead
    chars_to_remove = set("[]'\" ")  # Remove the escape sequence and use a set
    
    for char in chars_to_remove:
        user_id = user_id.replace(char, '')
    
    return user_id

#Verify a file is writable
def verify_file_permissions(filename):
    """
    Verify that we can write to the specified file.
    Returns True if file is writable, False otherwise.
    """
    try:
        # Try to open file in append mode
        with open(filename, 'a') as f:
            pass
        return True
    except IOError:
        logging.error(f"File {filename} is not writable")
        return False

def verify_character_data(filename='characters.json'):
    """Debug helper to verify character data in file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logging.info(f"Character file contents:")
        logging.info(f"Number of characters: {len(data)}")
        for user_id, char_data in data.items():
            logging.info(f"User ID: {user_id} (type: {type(user_id)})")
            logging.info(f"Character name: {char_data.get('Name')}")
            
        return True
    except Exception as e:
        logging.error(f"Error verifying character data: {e}")
        return False

def initialize_game_data():
    """Initialize all game data at startup."""
    global game_data, area_lookup, items, npcs, actions, characters
    try:
        game_data = load_game_data()
        if game_data:
            area_lookup = game_data.get('areas', {})
            items = game_data.get('items', {})
            npcs = game_data.get('npcs', {})
            actions = game_data.get('actions', {})
            characters = game_data.get('characters', {})
        
            # Verify data loading
            logging.info(f"Initialized with:")
            logging.info(f"- {len(items)} items")
            logging.info(f"- {len(area_lookup)} areas")
            logging.info(f"- {len(npcs)} NPCs")
            logging.info(f"- {len(actions)} actions")
            logging.info(f"- {len(characters)} characters")
        
            return True
    except Exception as e:
        logging.error(f"Failed to initialize game data: {e}", exc_info=True)
        return False

def save_world(world, filename=WORLD_FILE):
    data = world.to_dict()
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def save_areas(areas, filename=AREAS_FILE):
    data = {area.name: area.to_dict() for area in areas}
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def save_npcs(npcs, filename=NPCS_FILE):
    data = {npc.name: npc.to_dict() for npc in npcs}
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

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
    """Calculate travel time in seconds"""
    try:
        if not character.current_area or not destination_area:
            return 0
            
        distance = calculate_distance(character.current_area.coordinates, destination_area.coordinates)
        speed = character.movement_speed
        
        if speed == 0:
            return float('inf')
            
        # Convert distance and speed to determine seconds of travel
        travel_time = (distance / speed) * 60  # Convert to seconds
        
        return travel_time
        
    except Exception as e:
        logging.error(f"Error calculating travel time: {e}")
        return 0

# Helper function to get the correct channel for a guild
async def get_guild_game_channel(guild_id: int, channel_type: str = 'game'):
    """
    Get the appropriate channel for a guild.
    Args:
        guild_id (int): The guild ID
        channel_type (str): The type of channel to get ('game', 'announcements', etc.)
    Returns:
        discord.TextChannel or None
    """
    try:
        if guild_id not in GUILD_CONFIGS:
            logging.error(f"No configuration found for guild {guild_id}")
            return None
            
        channel_id = GUILD_CONFIGS[guild_id]['channels'].get(channel_type)
        if not channel_id:
            logging.error(f"No {channel_type} channel configured for guild {guild_id}")
            return None

        channel = bot.get_channel(channel_id)
        if not channel:
            channel = await bot.fetch_channel(channel_id)
            
        return channel
    except Exception as e:
        logging.error(f"Error getting channel for guild {guild_id}: {e}")
        return None

# Helper function to create scene embed
def create_scene_embed(area):
    """Creates an embed for scene description"""
    try:
        embed = discord.Embed(
            title=area.name,
            description=area.description,
            color=discord.Color.green()
        )

        # Connected Areas
        if hasattr(area, 'connected_areas') and area.connected_areas:
            connected_area_names = ', '.join(f"**{connected_area.name}**" 
                                           for connected_area in area.connected_areas)
            embed.add_field(
                name="Connected Areas",
                value=connected_area_names,
                inline=False
            )
        else:
            embed.add_field(name="Connected Areas", value="None", inline=False)

        # NPCs
        if hasattr(area, 'npcs') and area.npcs:
            npc_names = ', '.join(f"**{npc.name}**" for npc in area.npcs)
            embed.add_field(name="NPCs Present", value=npc_names, inline=False)
        else:
            embed.add_field(name="NPCs Present", value="None", inline=False)

        # Items
        if hasattr(area, 'inventory') and area.inventory:
            item_names = ', '.join(f"**{item.name}**" 
                                 for item in area.inventory if hasattr(item, 'name'))
            embed.add_field(
                name="Items Available",
                value=item_names if item_names else "None",
                inline=False
            )
        else:
            embed.add_field(name="Items Available", value="None", inline=False)

        return embed
    except Exception as e:
        logging.error(f"Error creating scene embed: {e}", exc_info=True)
        return None

async def travel_task(bot, character, user_id, characters, save_characters):
    """Handle the travel process and arrival"""
    try:
        current_time = time.time()
        if character.travel_end_time > current_time:
            wait_time = character.travel_end_time - current_time
            await asyncio.sleep(wait_time)

        # Update character's status
        character.is_traveling = False
        previous_area = character.current_area
        character.move_to_area(character.travel_destination)
        destination_area = character.travel_destination
        character.travel_destination = None
        character.travel_end_time = None

        # Create arrival embed
        arrival_embed = discord.Embed(
            title="🏁 Arrival Notice",
            description=f"You have arrived at **{character.current_area.name}**!",
            color=discord.Color.green()
        )
        
        # Add area description
        if character.current_area.description:
            arrival_embed.add_field(
                name="Area Description",
                value=character.current_area.description,
                inline=False
            )

        # Add connected areas
        if character.current_area.connected_areas:
            connected = ", ".join(f"**{area.name}**" for area in character.current_area.connected_areas)
            arrival_embed.add_field(
                name="Connected Areas",
                value=f"You can travel to: {connected}",
                inline=False
            )

        # Send arrival notice in DM
        try:
            if hasattr(character, 'last_travel_message') and character.last_travel_message:
                try:
                    await character.last_travel_message.edit(embed=arrival_embed)
                    character.last_travel_message = None
                except Exception:
                    user = await bot.fetch_user(int(user_id))
                    if user:
                        await user.send(embed=arrival_embed)
            else:
                user = await bot.fetch_user(int(user_id))
                if user:
                    await user.send(embed=arrival_embed)
        except Exception as e:
            logging.error(f"Error sending arrival notice: {e}")

        # Create and send scene embed
        try:
            logging.info(f"Creating scene embed for {character.current_area.name}")
            scene_embed = create_scene_embed(character.current_area)
            
            # Verify bot is connected
            if not bot.is_ready():
                logging.error("Bot is not ready")
                return

            # Get channel
            channel_id = get_guild_game_channel(character.last_interaction_guild)
            channel = bot.get_channel(channel_id)
            if not channel:
                channel = await bot.fetch_channel(channel_id)
            
            if channel:
                logging.info(f"Sending scene embed to channel {channel_id}")
                # Check permissions
                permissions = channel.permissions_for(channel.guild.me)
                if not permissions.send_messages:
                    logging.error("Bot doesn't have permission to send messages in this channel")
                    return
                    
                # Try sending the message
                message = await channel.send(
                    content=f"**{character.name}** has arrived in **{character.current_area.name}**",
                    embed=scene_embed
                )
                if message:
                    logging.info("Scene embed sent successfully")
                else:
                    logging.error("Failed to send scene embed - no message returned")
            else:
                logging.error(f"Could not find channel with ID {channel_id}")
                
        except discord.Forbidden as e:
            logging.error(f"Bot lacks permissions to send messages: {e}")
        except discord.HTTPException as e:
            logging.error(f"HTTP error sending scene embed: {e}")
        except Exception as e:
            logging.error(f"Error sending scene description: {e}", exc_info=True)

        # Update character data
        characters[user_id] = character
        save_characters(characters)

    except Exception as e:
        logging.error(f"Error in travel_task for user '{user_id}': {e}", exc_info=True)

def load_actions():
    """
    Loads actions from the ACTIONS_FILE file.
    Returns:
        dict: A dictionary mapping actions to their associated stats.
    """
    try:
        with open(ACTIONS_FILE, 'r') as f:
            actions = json.load(f)
            logging.info("ACTIONS_FILE loaded successfully.")
            return actions
    except FileNotFoundError:
        logging.error("ACTIONS_FILE file not found.")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding ACTIONS_FILE: {e}")
        return {}


######################
#    Game Objects    #
######################

# Dictionary mapping channel IDs to Area instances
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
        self.Name = name
        self.Weight = weight
        self.Type = item_type
        self.Description = description
        self.Effect = effect
        self.Proficiency_Needed = proficiency_needed
        self.Average_Cost = average_cost
        self.Is_Magical = is_magical
        self.Rarity = rarity

    def to_dict(self):
        """Convert Item instance to dictionary."""
        return {
            'Name': self.Name,
            'Weight': self.Weight,
            'Type': self.Type,
            'Description': self.Description,
            'Effect': self.Effect,
            'Proficiency_Needed': self.Proficiency_Needed,
            'Average_Cost': self.Average_Cost,
            'Is_Magical': self.Is_Magical,
            'Rarity': self.Rarity
        }

    @classmethod
    def from_dict(cls, data):
        try:
            name = data.get('Name')
            if not name:
                raise ValueError("Item name is required")
                
            weight = data.get('Weight', 0)
            if not isinstance(weight, (int, float)):
                logging.warning(f"Invalid weight for item {name}, defaulting to 0")
                weight = 0
                
            item_type = data.get('Type')
            if not item_type:
                logging.warning(f"No type specified for item {name}, defaulting to 'Item'")
                item_type = 'Item'
                
            return cls(
                name=name,
                weight=weight,
                item_type=item_type,
                description=data.get('Description', 'No description available'),
                effect=data.get('Effect'),
                proficiency_needed=data.get('Proficiency_Needed'),
                average_cost=data.get('Average_Cost', 0),
                is_magical=data.get('Is_Magical', False),
                rarity=data.get('Rarity', 'Common')
            )
        except Exception as e:
            logging.error(f"Error creating item from data: {e}")
            raise

    def get_items_by_type(item_lookup, item_type):
            """Get all items of a specific type."""
            return {name: item for name, item in item_lookup.items() 
                    if item.Type.lower() == item_type.lower()}

    def get_magical_items(item_lookup):
        """Get all magical items."""
        return {name: item for name, item in item_lookup.items() 
                if item.Is_Magical}

    def get_items_by_rarity(item_lookup, rarity):
        """Get all items of a specific rarity."""
        return {name: item for name, item in item_lookup.items() 
                if item.Rarity.lower() == rarity.lower()}
    
    def update(self, **kwargs):
            """Update the item's attributes."""
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)


class InventoryMixin:
    def __init__(self, inventory=None, capacity=None):
        self.inventory = inventory if inventory is not None else []
        self.capacity = capacity

    def add_item_to_inventory(self, item: Item) -> None:
        if not isinstance(item, Item):
            raise TypeError("Only items of type 'Item' can be added to the inventory.")
        if self.can_add_item(item):
            self.inventory.append(item)
            print(f"Added {item.Name} to {self.__class__.__name__}'s inventory.")
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
    def __init__(self, damage_amount, damage_type, equip = True, **kwargs):
        super().__init__(item_type='Weapon', **kwargs)
        self.equip = equip
        self.damage_amount = damage_amount
        self.damage_type = damage_type
        self.effect = {'Damage_Amount': self.damage_amount, 'Damage_Type': self.damage_type}
    
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'Damage_Amount': self.damage_amount,
            'Damage_Type': self.damage_type,
            'Equip': self.equip
        })
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['Name', ''],
            weight=data['Weight', ''],
            description=data.get('Description', ''),
            effect=data.get('Effect'),
            proficiency_needed=data.get('Proficiency_Needed', ''),
            average_cost=data.get('Average_Cost', 0),
            is_magical=data.get('Is_Magical', False),
            rarity=data.get('Rarity', 'Common'),
            damage_amount=data['Damage_Amount', ''],
            damage_type=data['Damage_Type', ''],
            equip=data["Equip", '']
        )

class Armor(Item):
    def __init__(self, ac_value, max_dex_bonus, equip = True, **kwargs):
        super().__init__(item_type='Armor', **kwargs)
        self.ac_value = ac_value
        self.equip = equip
        self.max_dex_bonus = max_dex_bonus
        self.effect = {'AC': self.ac_value, 'Max_Dex_Bonus': self.max_dex_bonus}
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'AC_value': self.ac_value,
            'Max_Dex_Bonus': self.max_dex_bonus,
            "Equip": self.equip
        })
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['Name', ''],
            weight=data['Weight', 0],
            description=data.get('Description', ''),
            effect=data.get('Effect'),
            proficiency_needed=data.get('Proficiency_Needed'),
            average_cost=data.get('Average_Cost', 0),
            is_magical=data.get('Is_Magical', False),
            rarity=data.get('Rarity', 'Common'),
            ac_value=data['AC_value', 0 ],
            max_dex_bonus=data['Max_Dex_Bonus', 0],
            equip=data["Equip", '']
        )

class Shield(Item):
    def __init__(self, ac_value, max_dex_bonus, equip = True, **kwargs):
        super().__init__(item_type='Shield', **kwargs)
        self.ac_value = ac_value
        self.equip = equip
        self.effect = {'AC': self.ac_value}
    
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'AC_value': self.ac_value,
            'Equip': self.equip,
        })
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['Name', ''],
            weight=data['Weight', 0],
            description=data.get('Description', ''),
            effect=data.get('Effect', ''),
            proficiency_needed=data.get('Proficiency_Needed'),
            average_cost=data.get('Average_Cost', 0),
            is_magical=data.get('Is_Magical', False),
            rarity=data.get('Rarity', 'Common'),
            ac_value=data['AC_value', 0],
            max_dex_bonus=data['Max_Dex_Bonus', 0],
            equip=data["Equip", '']
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

    def update(self, **kwargs):
        """Update the world's attributes."""
        for key, value in kwargs.items():
            if key == 'Continents':
                # Expecting a list of Continent instances
                if isinstance(value, list):
                    self.continents = value
            elif hasattr(self, key):
                setattr(self, key, value)

    def add_continent(self, continent):
        """Add a continent to the world."""
        if continent not in self.continents:
            self.continents.append(continent)

    def remove_continent(self, continent):
        """Remove a continent from the world."""
        if continent in self.continents:
            self.continents.remove(continent)
    
    def to_dict(self):
        return {
            'Name': self.name,
            'Description': self.description,
            'Continents': self.continent_names
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['Name', ''],
            description=data.get('Description', ''),
            continents=None  # Will be set after loading Continents
        )
    
def load_world(continent_lookup, filename=WORLD_FILE):
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    world = World.from_dict(data)
    # Resolve continents
    world.continents = [continent_lookup[name] for name in world.continent_names if name in continent_lookup]
    return world

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
            'Name': self.name,
            'Description': self.description,
            'Coordinates': self.coordinates,
            'Regions': self.region_names
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['Name', ''],
            description=data.get('Description', ''),
            coordinates=tuple(data.get('Coordinates', (0, 0))),
            regions=None  # Will be set after loading Regions
        )
    
    def update(self, **kwargs):
        """Update the continent's attributes."""
        for key, value in kwargs.items():
            if key == 'regions':
                # Expecting a list of Region instances
                if isinstance(value, list):
                    self.regions = value
            elif hasattr(self, key):
                setattr(self, key, value)

    def add_region(self, region):
        """Add a region to the continent."""
        if region not in self.regions:
            self.regions.append(region)

    def remove_region(self, region):
        """Remove a region from the continent."""
        if region in self.regions:
            self.regions.remove(region)
    
def load_continents(region_lookup, filename=CONTINENTS_FILE):
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    continent_lookup = {}
    for continent_name, continent_data in data.items():
        continent = Continent.from_dict(continent_data)
        # Resolve regions
        continent.regions = [region_lookup[name] for name in continent.region_names if name in region_lookup]
        continent_lookup[continent_name] = continent
    return continent_lookup

class Region:
    def __init__(self, name, description=None, locations=None, coordinates=(0, 0)):
        self.coordinates = coordinates  # (x, y)
        self.name = name
        self.description = description
        self.locations = locations if locations is not None else []

    def update(self, **kwargs):
        """Update the region's attributes."""
        for key, value in kwargs.items():
            if key == 'Locations':
                # Expecting a list of Location instances
                if isinstance(value, list):
                    self.locations = value
            elif hasattr(self, key):
                setattr(self, key, value)

    def add_location(self, location):
        """Add a location to the region."""
        if location not in self.locations:
            self.locations.append(location)

    def remove_location(self, location):
        """Remove a location from the region."""
        if location in self.locations:
            self.locations.remove(location)
    
    def to_dict(self):
        return {
            'Name': self.name,
            'Description': self.description,
            'Coordinates': self.coordinates,
            'Locations': self.locations
        }

    @classmethod
    def from_dict(cls, data):
        """
        Creates a Region instance from a dictionary.
        Args:
            data (dict): The Region data.
        Returns:
            Region: An instance of the Region class.
        """
        try:
            logging.debug(f"Parsing Region data: {data}")
            name = data.get('Name', '')
            description = data.get('Description', '')
            coordinates = tuple(data.get('Coordinates', [0, 0]))
            location_names = data.get('Location_Names', [])

            return cls(
                name=name,
                description=description,
                coordinates=coordinates,
                location_names=location_names,
                locations=None  # To be set after loading Locations
            )
        except KeyError as e:
            logging.error(f"Missing key {e} in Region data.")
            raise
        except Exception as e:
            logging.error(f"Error parsing Region data: {e}")
            raise
    
def load_regions(location_lookup, filename=REGIONS_FILE):
    """
    Loads Region data from the specified JSON file.
    Args:
        location_lookup (dict): A dictionary mapping location names to Location instances.
        filename (str): The path to the regions JSON file.
    Returns:
        dict: A dictionary mapping region names to Region instances.
    """
    try:
        logging.debug(f"Loading Regions from {filename}")
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        region_lookup = {}
        for region_name, region_data in data.items():
            try:
                region = Region.from_dict(region_data)
                # Resolve locations
                resolved_locations = []
                for loc_name in region.location_names:
                    location = location_lookup.get(loc_name)
                    if location:
                        resolved_locations.append(location)
                        logging.debug(f"Location '{loc_name}' added to Region '{region.name}'.")
                    else:
                        logging.warning(f"Location '{loc_name}' not found for Region '{region.name}'.")
                region.locations = resolved_locations
                region_lookup[region_name] = region
                logging.debug(f"Loaded Region: {region.name}")
            except Exception as e:
                logging.error(f"Error loading Region '{region_name}': {e}")
        return region_lookup
    except FileNotFoundError:
        logging.error(f"{filename} file not found.")
        return {}
    except Exception as e:
        logging.error(f"Error loading Regions: {e}")
        return {}


class Location:
    def __init__(self, name, description='', coordinates=(0, 0), area_names=None, connected_area_names=None,
                 inventory=None, npcs=None, channel_id=None, allows_intercontinental_travel=False):
        self.name = name
        self.description = description
        self.coordinates = coordinates
        self.area_names = area_names if area_names else []
        self.connected_area_names = connected_area_names if connected_area_names else []
        self.inventory = inventory if inventory else []
        self.npcs = npcs if npcs else []
        self.channel_id = channel_id
        self.allows_intercontinental_travel = allows_intercontinental_travel

    def add_area(self, area):
        """Add an area to the location."""
        if area not in self.areas:
            self.areas.append(area)

    def remove_area(self, area):
        """Remove an area from the location."""
        if area in self.areas:
            self.areas.remove(area)

    def to_dict(self):
        return {
            'Name': self.name,
            'Description': self.description,
            'Coordinates': list(self.coordinates),
            'Area_Names': self.area_names,
            'Connected_Areas': self.connected_area_names,
            'Inventory': [item.name for item in self.inventory],
            'NPCs': [npc.name for npc in self.npcs],
            'Channel_ID': self.channel_id,
            'Allows_Intercontinental_Travel': self.allows_intercontinental_travel
        }

    @classmethod
    def from_dict(cls, data, npc_lookup, item_lookup):
        """
        Creates a Location instance from a dictionary.
        Args:
            data (dict): The Location data.
            item_lookup (dict): A dictionary mapping item names to Item instances.
        Returns:
            Location: An instance of the Location class.
        """
        try:
            name = data.get('Name', '')
            description = data.get('Description', '')
            coordinates = tuple(data.get('Coordinates', [0, 0]))
            area_names = data.get('Area_Names', [])
            connected_area_names = data.get('Connected_Areas', [])
            inventory_names = data.get('Inventory', [])
            inventory = [item_lookup[item_name] for item_name in inventory_names if item_name in item_lookup]
            npc_names = data.get('NPCs', [])
            npcs = [npc_lookup[npc_name] for npc_name in npc_names if npc_name in npc_lookup]
            channel_id = data.get('Channel_ID')
            allows_intercontinental_travel = data.get('Allows_Intercontinental_Travel', False)

            return cls(
                name=name,
                description=description,
                coordinates=coordinates,
                area_names=area_names,
                connected_area_names=connected_area_names,
                inventory=inventory,
                npcs=npcs,
                channel_id=channel_id,
                allows_intercontinental_travel=allows_intercontinental_travel
            )
        except KeyError as e:
            logging.error(f"Missing key {e} in Location data.")
            raise
        except Exception as e:
            logging.error(f"Error parsing Location data: {e}")
            raise
    
    
def load_locations(area_lookup, npc_lookup, item_lookup, filename=LOCATIONS_FILE):
    """
    Loads Location data from the specified JSON file.
    Args:
        area_lookup (dict): A dictionary mapping area names to Area instances.
        npc_lookup (dict): A dictionary mapping NPC names to NPC instances.
        item_lookup (dict): A dictionary mapping item names to Item instances.
        filename (str): The path to the locations JSON file.
    Returns:
        dict: A dictionary mapping location names to Location instances.
    """
    try:
        logging.debug(f"Loading Locations from {filename}")
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        location_lookup = {}
        for location_name, location_data in data.items():
            try:
                location = Location.from_dict(location_data, item_lookup, npc_lookup)
                location_lookup[location_name] = location
                logging.debug(f"Loaded Location: {location_name}")
            except Exception as e:
                logging.error(f"Error loading Location '{location_name}': {e}")
        return location_lookup
    except FileNotFoundError:
        logging.error(f"{filename} file not found.")
        return {}
    except Exception as e:
        logging.error(f"Error loading Locations: {e}")
        return {}

class Area:
    def __init__(self, name, description='', coordinates=(0, 0), connected_area_names=None, connected_areas=None,
                 inventory=None, npc_names=None, channel_id=None, allows_intercontinental_travel=False, npcs=None, **kwargs):
        self.name = name
        self.description = description
        self.coordinates = coordinates
        self.connected_area_names = connected_area_names if connected_area_names else []
        self.connected_areas = []  # To be populated after loading all areas
        self.inventory = inventory if inventory else []
        self.npc_names = npc_names if npc_names else []
        self.npcs = []  # To be populated after loading NPCs
        self.channel_id = channel_id
        self.allows_intercontinental_travel = allows_intercontinental_travel

    def to_dict(self):
            return {
                'Name': self.name,
                'Description': self.description,
                'Coordinates': list(self.coordinates),
                'Connected_Areas': [area.name for area in self.connected_areas],
                'Inventory': [item.name for item in self.inventory],
                'NPCs': [npc.name for npc in self.npcs],
                'Channel_ID': self.channel_id,
                'Allows_Intercontinental_Travel': self.allows_intercontinental_travel
            }
        
    @classmethod
    def from_dict(cls, data, item_lookup):
        """
        Creates an Area instance from a dictionary.
        Args:
            data (dict): The Area data.
            item_lookup (dict): A dictionary mapping item names to Item instances.
        Returns:
            Area: An instance of the Area class.
        """
        try:
            name = data.get('Name', '')
            description = data.get('Description', '')
            coordinates = tuple(data.get('Coordinates', [0, 0]))
            connected_area_names = data.get('Connected_Areas', [])
            inventory_names = data.get('Inventory', [])
            inventory=[item_lookup[item_name] for item_name in data.get('Inventory', []) if item_name in item_lookup],
            npc_names = data.get('NPCs', [])
            channel_id = data.get('Channel_ID', [])
            allows_intercontinental_travel = data.get('Allows_Intercontinental_Travel', False)

            return cls(
                name=name,
                description=description,
                coordinates=coordinates,
                connected_area_names=connected_area_names,
                inventory=inventory,
                npc_names=npc_names,
                channel_id=channel_id,
                allows_intercontinental_travel=allows_intercontinental_travel
            )
        except KeyError as e:
            logging.error(f"Missing key {e} in Area data.")
            raise
        except Exception as e:
            logging.error(f"Error parsing Area data: {e}")
            raise
    
    def update(self, **kwargs):
        """Update the area's attributes."""
        for key, value in kwargs.items():
            if key == 'Inventory':
                # Expecting a list of Item instances
                if isinstance(value, list):
                    self.inventory = value
            elif key == 'NPCs':
                # Expecting a list of NPC instances
                if isinstance(value, list):
                    self.npcs = value
            elif key == 'Connected_Areas':
                # Expecting a list of Area instances
                if isinstance(value, list):
                    self.connected_areas = value
            elif hasattr(self, key):
                setattr(self, key, value)

    def add_npc(self, npc):
        """Add an NPC to the area."""
        if npc not in self.npcs:
            self.npcs.append(npc)

    def remove_npc(self, npc):
        """Remove an NPC from the area."""
        if npc in self.npcs:
            self.npcs.remove(npc)

    def add_item(self, item):
        """Add an item to the area's inventory."""
        if item not in self.inventory:
            self.inventory.append(item)

    def remove_item(self, item):
        """Remove an item from the area's inventory."""
        if item in self.inventory:
            self.inventory.remove(item)

    def connect_area(self, area):
        """Connect another area to this one."""
        if area not in self.connected_areas:
            self.connected_areas.append(area)
            area.connected_areas.append(self)  # Assuming bidirectional connection

    def disconnect_area(self, area):
        """Disconnect another area from this one."""
        if area in self.connected_areas:
            self.connected_areas.remove(area)
            area.connected_areas.remove(self)  # Assuming bidirectional connection

    def add_connected_area(self, area, bidirectional=True, coordinates=(0, 0)):
        if area not in self.connected_areas:
            self.connected_areas.append(area,coordinates)
            area.connected_areas.append(self)  # Assuming bidirectional connection
    
    def get_npc(self, npc_name):
        for npc in self.npcs:
            if npc.name.lower() == npc_name.lower():
                return npc
        return None
    


# Function to retrieve an Area by name
def get_area_by_name(area_name, area_lookup):
    area = area_lookup.get(area_name)
    if not area:
        raise ValueError(f"Area '{area_name}' does not exist.")
    return area


class Entity(InventoryMixin):
    def __init__(self, name=None, stats=None, inventory=None, **kwargs):
        super().__init__(inventory=inventory)  # Call InventoryMixin's __init__
        self.name = name
        self.stats = stats if stats else {}

    def get_stat_modifier(self, stat):
        return (self.stats.get(stat, 10) - 10) // 2

class Character(Entity):
    """
    Represents a player's character with various attributes.
    """
    def __init__(self, user_id, name=None, species=None, char_class=None, gender=None, pronouns=None, description=None, stats=None, skills=None, inventory=None, equipment=None, currency=None, spells=None, abilities=None, ac=None, max_hp=1, curr_hp=1, movement_speed=None, travel_end_time=None, spellslots=None, level=None, xp=None, reputation=None, is_traveling=False, current_area=None, current_location=None, current_region=None, current_continent=None, current_world=None, area_lookup=None, capacity=None, **kwargs):
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
        capacity = capacity if capacity else 150  # Default capacity of 150 lbs
        self.skills = skills if skills else {}
        self.inventory = inventory if inventory else {}
        self.equipment = equipment if equipment else {
            'Armor': None,
            'Left_Hand': None,
            'Right_Hand': None,
            'Belt_Slots': [None]*4,
            'Back': None,
            'Magic_Slots': [None]*3
        }
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
        """
        Convert Character instance to a dictionary.
        """
        try:
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
                'Inventory': {k: v.to_dict() if hasattr(v, 'to_dict') else str(v) 
                            for k, v in self.inventory.items()} if self.inventory else {},
                'Equipment': {
                    'Armor': self.equipment['Armor'].to_dict() if self.equipment.get('Armor') else None,
                    'Left_Hand': self.equipment['Left_Hand'].to_dict() if self.equipment.get('Left_Hand') else None,
                    'Right_Hand': self.equipment['Right_Hand'].to_dict() if self.equipment.get('Right_Hand') else None,
                    'Belt_Slots': [item.to_dict() if item else None for item in self.equipment['Belt_Slots']],
                    'Back': self.equipment['Back'].to_dict() if self.equipment.get('Back') else None,
                    'Magic_Slots': [item.to_dict() if item else None for item in self.equipment['Magic_Slots']]
                },
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
                'Last_Interaction_Guild': self.last_interaction_guild  # Add this line
            }
            return base_dict
                
        except Exception as e:
            logging.error(f"Error in Character.to_dict: {e}")
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

def check_travel_completion(character):
    """
    Check if a character has completed their travel.
    Args:
        character (Character): The character to check
    Returns:
        bool: True if travel completed, False otherwise
    """
    try:
        if not character.is_traveling:
            return False

        current_time = time.time()
        if current_time >= character.travel_end_time:
            # Complete the travel
            if character.move_to_area(character.travel_destination):
                character.is_traveling = False
                character.travel_destination = None
                character.travel_end_time = None
                logging.info(f"Character '{character.name}' completed travel.")
                return True
            else:
                logging.error(f"Failed to complete travel for character '{character.name}'.")
                
        return False

    except Exception as e:
        logging.error(f"Error checking travel completion for character '{character.name}': {e}")
        return False

def save_characters(characters_dict: dict[str, Character], filename='characters.json'):
    try:
        # Convert characters to dictionary format with cleaned IDs
        data = {
            clean_user_id(user_id): char.to_dict() 
            for user_id, char in characters_dict.items()
        }
        
        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        # Update cache with cleaned IDs
        character_cache = {
            clean_user_id(user_id): char 
            for user_id, char in characters_dict.items()
        }
        last_cache_update = time.time()
        
        logging.info(f"Successfully saved {len(characters_dict)} characters")
        
    except Exception as e:
        logging.error(f"Failed to save characters: {e}")
        raise


# Point-Buy System Configuration
POINT_BUY_TOTAL = 15
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
    def __init__(self, name=None, role=None, inventory=None, capacity=None, 
                 stats=None, movement_speed=None, travel_end_time=None, 
                 max_hp=None, curr_hp=None, spellslots=None, ac=None,
                 abilities=None, spells=None, attitude=None, faction=None, 
                 reputation=None, relations=None, dialogue=None, 
                 description=None, is_hostile=None, current_area=None, **kwargs):
        # Call Entity's __init__ with name parameter
        super().__init__(name=name, stats=stats, inventory=inventory, **kwargs)
        self.role = role
        self.movement_speed = movement_speed
        self.travel_end_time = travel_end_time
        self.max_hp = max_hp
        self.curr_hp = curr_hp
        self.spellslots = spellslots
        self.ac = ac
        self.abilities = abilities if abilities else {}
        self.spells = spells if spells else {}
        self.attitude = attitude
        self.faction = faction
        self.reputation = reputation
        self.relations = relations if relations else {}
        self.dialogue = dialogue if dialogue else []
        self.description = description
        self.is_hostile = is_hostile if is_hostile is not None else False
        self.current_area = current_area if current_area else "The Void"

    def to_dict(self):
        return {
            'Name': self.name,
            'Description': self.description,
            'Dialogue': self.dialogue,
            'Inventory': [item.to_dict() for item in self.inventory],
            'Stats': self.stats,
            'Is_Hostile': self.is_hostile,
            'Role': self.role,
            'Movement_Speed': self.movement_speed,
            'Travel_End_Time': self.travel_end_time,
            'Max_HP': self.max_hp,
            'Curr_HP': self.curr_hp,
            'Spellslots': self.spellslots,
            'AC': self.ac,
            'Abilities': self.abilities,
            'Spells': self.spells,
            'Attitude': self.attitude,
            'Faction': self.faction,
            'Reputation': self.reputation,
            'Relations': self.relations
        }
          
    @classmethod
    def from_dict(cls, data, item_lookup):
        try:
            logging.debug(f"Creating NPC from data: {data}")
            name = data.get('Name')
            if not name:
                logging.error("No name provided in NPC data")
                raise ValueError("NPC name is required")
                
            inventory_names = data.get('Inventory', [])
            inventory = [item_lookup[item_name] for item_name in inventory_names 
                        if item_name in item_lookup]
            
            npc = cls(
                name=name,  # Make sure name is passed
                description=data.get('Description', ''),
                role=data.get('Role'),
                dialogue=data.get('Dialogue', []),
                inventory=inventory,
                stats=data.get('Stats', {}),
                is_hostile=data.get('Is_Hostile', False),
                movement_speed=data.get('Movement_Speed'),
                travel_end_time=data.get('Travel_End_Time'),
                max_hp=data.get('Max_HP'),
                curr_hp=data.get('Curr_HP'),
                spellslots=data.get('Spellslots'),
                ac=data.get('AC'),
                abilities=data.get('Abilities'),
                spells=data.get('Spells'),
                attitude=data.get('Attitude'),
                faction=data.get('Faction'),
                reputation=data.get('Reputation'),
                relations=data.get('Relations')
            )
            logging.debug(f"Successfully created NPC: {name}")
            return npc
        except Exception as e:
            logging.error(f"Error creating NPC: {e}")
            raise

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
        
    def update(self, **kwargs):
        """Update the NPC's attributes."""
        for key, value in kwargs.items():
            if key == 'Inventory':
                # Expecting a list of Item instances
                if isinstance(value, list):
                    self.inventory = value
            elif hasattr(self, key):
                setattr(self, key, value)


def resolve_area_connections_and_npcs(area_lookup, npc_lookup):
    """
    Resolves the connected areas and NPCs for each Area instance.
    Args:
        area_lookup (dict): A dictionary mapping area names to Area instances.
        npc_lookup (dict): A dictionary mapping NPC names to NPC instances.
    """
    try:
        # Debug output to see what we're working with
        logging.debug("Starting area and NPC resolution")
        logging.debug(f"Available areas: {list(area_lookup.keys())}")
        logging.debug(f"Available NPCs: {list(npc_lookup.keys())}")

        for area in area_lookup.values():
            logging.debug(f"\nProcessing area: {area.name}")
            logging.debug(f"Looking for connected areas: {area.connected_area_names}")
            logging.debug(f"Looking for NPCs: {area.npc_names}")

            # Resolve connected areas
            resolved_areas = []
            for name in area.connected_area_names:
                connected_area = area_lookup.get(name)
                if not connected_area:
                    # Try case-insensitive search
                    for area_key in area_lookup.keys():
                        if area_key.lower() == name.lower():
                            connected_area = area_lookup[area_key]
                            break
                
                if connected_area:
                    resolved_areas.append(connected_area)
                    logging.debug(f"Successfully connected area '{area.name}' to '{name}'")
                else:
                    logging.warning(f"Connected area '{name}' not found for area '{area.name}'")
            
            area.connected_areas = resolved_areas

            # Resolve NPCs
            resolved_npcs = []
            for npc_name in area.npc_names:
                npc = npc_lookup.get(npc_name)
                if not npc:
                    # Try case-insensitive search
                    for npc_key in npc_lookup.keys():
                        if npc_key.lower() == npc_name.lower():
                            npc = npc_lookup[npc_key]
                            break
                
                if npc:
                    resolved_npcs.append(npc)
                    logging.debug(f"Successfully added NPC '{npc_name}' to area '{area.name}'")
                else:
                    logging.warning(f"NPC '{npc_name}' not found for area '{area.name}'")
                    logging.debug(f"Available NPCs were: {list(npc_lookup.keys())}")
            
            area.npcs = resolved_npcs

        logging.info("Completed area and NPC resolution")
        return True

    except Exception as e:
        logging.error(f"Error in resolve_area_connections_and_npcs: {e}", exc_info=True)
        return False


# ---------------------------- #
#      UI Component Classes    #
# ---------------------------- #

def create_character_progress_embed(user_id: str, current_step: int) -> discord.Embed:
    """
    Creates a progress embed for character creation.
    Args:
        user_id (str): The user's ID
        current_step (int): Current step in character creation (1-7)
    Returns:
        discord.Embed: The formatted embed
    """
    session = character_creation_sessions.get(user_id, {})
    name = session.get('Name', 'Unknown')
    
    embed = discord.Embed(
        title="Character Creation",
        description=f"Creating character: **{name}**",
        color=discord.Color.blue()
    )
    
    # Add character info fields if they exist
    if session.get('Gender'):
        embed.add_field(name="Gender", value=session['Gender'], inline=True)
    if session.get('Pronouns'):
        embed.add_field(name="Pronouns", value=session['Pronouns'], inline=True)
    if session.get('Species'):
        embed.add_field(name="Species", value=session['Species'], inline=True)
    if session.get('Char_Class'):
        embed.add_field(name="Class", value=session['Char_Class'], inline=True)
    
    # Add description in a collapsible field if it exists
    if session.get('Description'):
        desc = session['Description']
        if len(desc) > 100:
            desc = desc[:97] + "..."
        embed.add_field(name="Description", value=desc, inline=False)
    
    # Create progress indicator
    steps = [
        ("Name", True if current_step > 1 else False),
        ("Gender", True if current_step > 2 else False),
        ("Pronouns", True if current_step > 3 else False),
        ("Description", True if current_step > 4 else False),
        ("Species", True if current_step > 5 else False),
        ("Class", True if current_step > 6 else False),
        ("Abilities", True if current_step > 7 else False)
    ]
    
    progress = "\n".join(
        f"Step {i+1}/7: {step[0]} {'✓' if step[1] else '⏳' if i == current_step-1 else ''}"
        for i, step in enumerate(steps)
    )
    
    embed.add_field(name="Progress", value=progress, inline=False)
    return embed

def update_character_embed(session_data, current_step):
    """Creates a consistent embed for character creation progress"""
    embed = discord.Embed(
        title="Character Creation",
        description=f"Creating character: **{session_data.get('Name', 'Unknown')}**",
        color=discord.Color.blue()
    )
    
    # Basic info fields
    if session_data.get('Gender'):
        embed.add_field(name="Gender", value=session_data['Gender'], inline=True)
    if session_data.get('Pronouns'):
        embed.add_field(name="Pronouns", value=session_data['Pronouns'], inline=True)
    if session_data.get('Species'):
        embed.add_field(name="Species", value=session_data['Species'], inline=True)
    if session_data.get('Char_Class'):
        embed.add_field(name="Class", value=session_data['Char_Class'], inline=True)
    
    # Progress bar
    steps = ["Name", "Gender", "Pronouns", "Description", "Species", "Class", "Abilities"]
    progress = ""
    for i, step in enumerate(steps):
        if i < current_step:
            progress += f"Step {i+1}/7: {step} ✓\n"
        elif i == current_step:
            progress += f"Step {i+1}/7: {step} ⏳\n"
        else:
            progress += f"Step {i+1}/7: {step}\n"
    
    embed.add_field(name="Progress", value=progress, inline=False)
    return embed

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
        global character_creation_sessions
        selected_gender = dropdown.values[0]
        character_creation_sessions[user_id]['Gender'] = selected_gender
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
        global character_creation_sessions
        selected_pronouns = dropdown.values[0]
        character_creation_sessions[user_id]['Pronouns'] = selected_pronouns
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
        global character_creation_sessions
        selected_species = dropdown.values[0]
        character_creation_sessions[user_id]['Species'] = selected_species
        logging.info(f"User {user_id} selected species: {selected_species}")

        # Proceed to class selection
        await interaction.response.edit_message(
            content=f"Species set to **{selected_species}**! Please select a class:",
            view=ClassSelectionView(user_id)
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in species_callback for user {user_id}: {e}")

async def start_ability_score_assignment(interaction: discord.Interaction, user_id: str):
    """
    Start the ability score assignment process for a character.
    """
    try:
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
            view=PhysicalAbilitiesView(user_id, area_lookup)
        )
        logging.info(f"Started ability score assignment for user {user_id}")
    except Exception as e:
        logging.error(f"Error starting ability score assignment for user {user_id}: {e}")
        await interaction.response.send_message(
            "An error occurred while starting ability score assignment. Please try again.",
            ephemeral=True
        )

async def class_callback(dropdown, interaction, user_id):
    try:
        global character_creation_sessions, items
        selected_class = dropdown.values[0]
        character_creation_sessions[user_id]['Char_Class'] = selected_class
       
        # Initialize equipment as a complete dictionary with all slots
        equipment = {
            'Armor': None,
            'Left_Hand': None,
            'Right_Hand': None,
            'Belt_Slots': [None] * 4,
            'Back': None,
            'Magic_Slots': [None] * 3
        }
       
        def get_item_safely(item_name):
            """Helper function to safely get and convert items"""
            item = items.get(item_name)
            if not item:
                logging.warning(f"Could not find item: {item_name}")
                return None
            if isinstance(item, dict):
                return Item.from_dict(item)
            if hasattr(item, 'to_dict'):
                return item
            logging.warning(f"Unknown item type for {item_name}: {type(item)}")
            return None

        # Add class-specific equipment using loaded items
        if selected_class == "Warrior":
            equipment.update({
                'Right_Hand': get_item_safely("Longsword"),
                'Left_Hand': get_item_safely("Wooden Shield"),
                'Armor': get_item_safely("Ringmail Armor")
            })
            inventory_items = [
                get_item_safely("Healing Potion"),
                get_item_safely("Bedroll"),
                get_item_safely("Tinderbox"),
                get_item_safely("Torch"),
                get_item_safely("Torch")
            ]
        elif selected_class == "Mage":
            equipment.update({
                'Right_Hand': get_item_safely("Staff"),
                'Left_Hand': get_item_safely("Dagger"),
                'Armor': get_item_safely("Robes")
            })
            inventory_items = [
                get_item_safely("Healing Potion"),
                get_item_safely("Bedroll"),
                get_item_safely("Tinderbox"),
                get_item_safely("Torch"),
                get_item_safely("Torch"),
                get_item_safely("Component Pouch")
            ]
        elif selected_class == "Rogue":
            equipment.update({
                'Right_Hand': get_item_safely("Dagger"),
                'Left_Hand': get_item_safely("Dagger"),
                'Armor': get_item_safely("Leather Armor")
            })
            inventory_items = [
                get_item_safely("Healing Potion"),
                get_item_safely("Bedroll"),
                get_item_safely("Tinderbox"),
                get_item_safely("Torch"),
                get_item_safely("Torch"),
                get_item_safely("Thieves Tools")
            ]
        elif selected_class == "Cleric":
            equipment.update({
                'Right_Hand': get_item_safely("Mace"),
                'Left_Hand': get_item_safely("Wooden Shield"),
                'Armor': get_item_safely("Studded Leather Armor")
            })
            inventory_items = [
                get_item_safely("Healing Potion"),
                get_item_safely("Bedroll"),
                get_item_safely("Tinderbox"),
                get_item_safely("Torch"),
                get_item_safely("Torch"),
                get_item_safely("Holy Symbol")
            ]

         # Log any missing items
        for slot, item in equipment.items():
            if item is None and slot not in ['Belt_Slots', 'Back', 'Magic_Slots']:
                logging.warning(f"Missing equipment item for slot {slot} in class {selected_class}")
       
        # Convert inventory list to dictionary
        inventory = {str(i): item for i, item in enumerate(inventory_items) if item is not None}
        
        # Update the session data - replace entire equipment dictionary
        character_creation_sessions[user_id]['Equipment'] = equipment
        character_creation_sessions[user_id]['Inventory'] = inventory
        logging.info(f"User {user_id} selected class: {selected_class} and received starting equipment")
        logging.debug(f"Equipment set: {equipment}")
        await start_ability_score_assignment(interaction, user_id)

    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        logging.error(f"Error in class_callback for user {user_id}: {e}")

def generate_ability_embed(user_id):
    """
    Generates an embed reflecting the current ability scores and remaining points.
    """
    try:
        global character_creation_sessions
        remaining_points = POINT_BUY_TOTAL - character_creation_sessions[user_id]['points_spent']
        assignments = character_creation_sessions[user_id]['Stats']

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
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.add_item(StartCharacterButton(bot))


class StartCharacterButton(discord.ui.Button):
    def __init__(self, bot):
        super().__init__(label="Start Character Creation", style=discord.ButtonStyle.green)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        global character_creation_sessions
        try:
            user_id = str(interaction.user.id)
            
            # Initialize session if it doesn't exist
            if character_creation_sessions is None:
                character_creation_sessions = {}
            
            if user_id not in character_creation_sessions:
                character_creation_sessions[user_id] = {'Stats': {}, 'points_spent': 0}

            # Create initial embed
            embed = discord.Embed(
                title="Character Creation - Ability Scores",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Remaining Points",
                value=f"{POINT_BUY_TOTAL}/{POINT_BUY_TOTAL}",
                inline=False
            )
            embed.set_footer(text="Assign your ability scores using the dropdowns below.")

            # Present the modal to get the character's name
            await interaction.response.send_modal(CharacterNameModal(user_id))
            
        except Exception as e:
            logging.error(f"Error in StartCharacterButton callback for user {user_id}: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An error occurred. Please try again.",
                    ephemeral=True
                )


class CharacterNameModal(discord.ui.Modal):
    def __init__(self, user_id):
        super().__init__(title="Enter Character Name")
        self.user_id = user_id
        self.character_name = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter your character's name...",
            min_length=2,
            max_length=32
        )
        self.add_item(self.character_name)

    async def on_submit(self, interaction: discord.Interaction):
        character_name = self.children[0].value
        character_creation_sessions[self.user_id]['Name'] = character_name
        
        # Create progress embed using the new function
        embed = create_character_progress_embed(self.user_id, 1)
        
        await interaction.response.send_message(
            content="Please select your gender:",
            embed=embed,
            view=GenderSelectionView(self.user_id),
            ephemeral=True
        )
        
        logging.info(f"User {self.user_id} entered name: {character_name}")

# Example of updating a callback function to use the progress embed
async def gender_callback(dropdown, interaction, user_id):
    try:
        selected_gender = dropdown.values[0]
        character_creation_sessions[user_id]['Gender'] = selected_gender
        
        # Create progress embed using the new function
        embed = create_character_progress_embed(user_id, 2)
        
        await interaction.response.edit_message(
            content=f"Please select your pronouns:",
            embed=embed,
            view=PronounsSelectionView(user_id)
        )
        
        logging.info(f"User {user_id} selected gender: {selected_gender}")
    except Exception as e:
        logging.error(f"Error in gender_callback for user {user_id}: {e}")
        await interaction.response.send_message(
            "An error occurred. Please try again.",
            ephemeral=True
        )
class DescriptionModal(discord.ui.Modal):
    def __init__(self, user_id):
        super().__init__(title="Enter Character Description")
        self.user_id = user_id
        self.description = discord.ui.TextInput(
            label="Character Description",
            placeholder="Describe your character's appearance, personality, and background...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            min_length=20
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
            await interaction.followup.send_modal(DescriptionModal(self.user_id))
            return
            
        # Save description using capitalized key
        character_creation_sessions[self.user_id]['Description'] = description
        
        # Create progress embed using the new function
        embed = create_character_progress_embed(self.user_id, 4)
        
        # Proceed to species selection
        await interaction.response.edit_message(
            content="Description set! Please select a species:",
            embed=embed,
            view=SpeciesSelectionView(self.user_id)
        )
        logging.info(f"User {self.user_id} provided description with {word_count} words.")


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
    def __init__(self, user_id, area_lookup):
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.physical_abilities = ['Strength', 'Dexterity', 'Constitution']
        
        for ability in self.physical_abilities:
            global character_creation_sessions
            current_score = character_creation_sessions[user_id]['Stats'].get(ability, None)
            self.add_item(AbilitySelect(user_id, ability, current_score))
        self.add_item(NextMentalAbilitiesButton(user_id, area_lookup))
        logging.info(f"PhysicalAbilitiesView created for user {user_id} with {len(self.children)} components.")


class MentalAbilitiesView(discord.ui.View):
    def __init__(self, user_id, area_lookup):
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.mental_abilities = ['Intelligence', 'Wisdom', 'Charisma']
        for ability in self.mental_abilities:
            global character_creation_sessions
            current_score = character_creation_sessions[user_id]['Stats'].get(ability, None)
            self.add_item(AbilitySelect(user_id, ability, current_score))
        self.add_item(BackPhysicalAbilitiesButton(user_id))
        self.add_item(FinishAssignmentButton(user_id, self.area_lookup))
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
            global character_creation_sessions
            selected_score = int(self.values[0])
            cost = calculate_score_cost(selected_score)
            user_id = self.user_id
            cur_view=self.view
            cur_message=interaction.message.content
            
            # Retrieve previous score and cost
            previous_score = character_creation_sessions[user_id]['Stats'].get(self.ability_name, 10)
            previous_cost = calculate_score_cost(previous_score)

            # Update the session data
            character_creation_sessions[user_id]['Stats'][self.ability_name] = selected_score
            character_creation_sessions[user_id]['points_spent'] += (cost - previous_cost)
            logging.info(f"User {user_id} set {self.ability_name} to {selected_score}. Cost: {cost}. Total points spent: {character_creation_sessions[user_id]['points_spent']}.")

            remaining_points = POINT_BUY_TOTAL - character_creation_sessions[user_id]['points_spent']

            if remaining_points < 0:
                # Revert the assignment
                character_creation_sessions[user_id]['Stats'][self.ability_name] = previous_score
                character_creation_sessions[user_id]['points_spent'] -= (cost - previous_cost)
                await interaction.response.send_message(
                    f"Insufficient points to assign **{selected_score}** to **{self.ability_name}**. You have **{remaining_points + (cost - previous_cost)} points** remaining.",
                    ephemeral=True
                )
                logging.warning(f"User {user_id} overspent points while assigning {self.ability_name}.")
                return

            current_score=character_creation_sessions[user_id]['Stats'].get(self.ability_name, 10),

            # Determine which view to recreate
            if isinstance(self.view, PhysicalAbilitiesView):
                new_view = PhysicalAbilitiesView(user_id, area_lookup)
            elif isinstance(self.view, MentalAbilitiesView):
                new_view = MentalAbilitiesView(user_id, area_lookup)
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
    def __init__(self, user_id, area_lookup):
        super().__init__(label="Next", style=discord.ButtonStyle.blurple)
        self.user_id = user_id
        self.area_lookup = area_lookup

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id
            global character_creation_sessions
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
                view=MentalAbilitiesView(user_id, self.area_lookup),
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
                view=PhysicalAbilitiesView(user_id, area_lookup),
                embed=embed 
            )
            logging.info(f"User {user_id} navigated back to PhysicalAbilitiesView.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error in BackPhysicalAbilitiesButton callback for user {self.user_id}: {e}")

class ConfirmationView(discord.ui.View):
    def __init__(self, user_id, area_lookup):
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.add_item(discord.ui.Button(
            label="Confirm", 
            style=discord.ButtonStyle.green,
            custom_id="confirm"
        ))
        self.add_item(discord.ui.Button(
            label="Cancel", 
            style=discord.ButtonStyle.red,
            custom_id="cancel"
        ))

    async def callback(self, interaction: discord.Interaction):
        if interaction.custom_id == "confirm":
            # Proceed with character creation
            await finalize_character(interaction, self.user_id, self.area_lookup)
        else:
            # Return to ability scores
            await interaction.response.edit_message(
                content="Returning to ability scores...",
                view=MentalAbilitiesView(self.user_id, self.area_lookup)
            )

class FinishAssignmentButton(discord.ui.Button):
    def __init__(self, user_id, area_lookup):
        super().__init__(label="Finish", style=discord.ButtonStyle.green)
        self.user_id = user_id
        self.area_lookup = area_lookup

    async def callback(self, interaction: discord.Interaction):
        try:
            global character_creation_sessions
            user_id = self.user_id
            allocation = character_creation_sessions[user_id]['Stats']
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
                view=FinalizeCharacterView(user_id, self.area_lookup),
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
    def __init__(self, user_id, area_lookup):
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.add_item(FinalizeCharacterButton(user_id, area_lookup))
        logging.info(f"FinalizeCharacterView created for user {user_id} with {len(self.children)} components.")

class FinalizeCharacterButton(discord.ui.Button):
    def __init__(self, user_id, area_lookup):
        super().__init__(label="Finish Character Creation", style=discord.ButtonStyle.green)
        self.user_id = user_id
        self.area_lookup = area_lookup

    async def callback(self, interaction: discord.Interaction):
        try:
            global character_creation_sessions
            user_id = self.user_id
            session = character_creation_sessions.get(user_id, {})

            if not session:
                await interaction.response.send_message("No character data found. Please start over.", ephemeral=True)
                logging.error(f"No character data found for user {user_id} during finalization.")
                return

            allocation = session.get('Stats', {})
            is_valid, message = is_valid_point_allocation(allocation)
            if not is_valid:
                await interaction.response.send_message(f"Character creation failed: {message}", ephemeral=True)
                logging.warning(f"User {user_id} failed point allocation validation during finalization: {message}")
                return

            # Use self.area_lookup instead of area_lookup
            character = await finalize_character(interaction, user_id, self.area_lookup)
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
                
                # Add stats
                stats_text = "\n".join(f"{stat}: {value}" for stat, value in character.stats.items())
                embed.add_field(name="Stats", value=stats_text, inline=True)
                
                # Add equipment
                equipment_text = []
                for slot, item in character.equipment.items():
                    if isinstance(item, list):
                        # Handle belt slots and magic slots
                        items = [i.Name if hasattr(i, 'Name') else 'Empty' for i in item if i is not None]
                        equipment_text.append(f"{slot}: {', '.join(items) if items else 'Empty'}")
                    else:
                        # Handle regular equipment slots
                        item_name = item.Name if item and hasattr(item, 'Name') else 'Empty'
                        equipment_text.append(f"{slot}: {item_name}")
                embed.add_field(name="Equipment", value="\n".join(equipment_text), inline=True)
                
                # Add inventory
                if character.inventory:
                    inventory_text = []
                    for item_key, item in character.inventory.items():
                        if hasattr(item, 'Name'):
                            inventory_text.append(item.Name)
                        elif isinstance(item, dict) and 'Name' in item:
                            inventory_text.append(item['Name'])
                    inventory_display = "\n".join(inventory_text) if inventory_text else "Empty"
                else:
                    inventory_display = "Empty"
                embed.add_field(name="Inventory", value=inventory_display, inline=True)

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

async def finalize_character(interaction: discord.Interaction, user_id, area_lookup):
    """
    Finalizes the character creation by instantiating a Character object.
    Args:
        interaction (discord.Interaction): The interaction object.
        user_id (str): The user's ID.
    Returns:
        Character or None: The created Character object or None if failed.
    """
    global character_creation_sessions
    session = character_creation_sessions.get(user_id, {})
    if not session:
        await interaction.response.send_message("No character data found.", ephemeral=True)
        logging.error(f"No session data found for user {user_id} during finalization.")
        return None

    allocation = session.get('Stats', {})
    is_valid, message = is_valid_point_allocation(allocation)
    if not is_valid:
        await interaction.response.send_message(f"Character creation failed: {message}", ephemeral=True)
        logging.warning(f"User {user_id} failed point allocation validation: {message}")
        return None

    # Example area name to assign
    starting_area_name = DEFAULT_STARTING_AREA

    # Log available areas
    logging.debug(f"Available areas in area_lookup: {list(area_lookup.keys())}")

    # Retrieve the Area object
    starting_area = area_lookup.get(starting_area_name)

    if not starting_area:
        raise ValueError(f"Starting area '{starting_area_name}' does not exist in area_lookup.")

    # Create the Character instance
    character = Character(
        name=session.get('Name', "Unnamed Character"),
        user_id=session.get('User_ID', user_id),
        species=session.get('Species', "Unknown Species"),
        char_class=session.get('Char_Class', "Unknown Class"),
        gender=session.get('Gender', "Unspecified"),
        pronouns=session.get('Pronouns', "They/Them"),
        description=session.get('Description', "No description provided."),
        stats=session.get('Stats', {
            'Strength': 10,
            'Dexterity': 10,
            'Constitution': 10,
            'Intelligence': 10,
            'Wisdom': 10,
            'Charisma': 10
        }),
        skills=session.get('Skills', {}),
        inventory=session.get('Inventory', {}),
        equipment=session.get('Equipment', {}),
        currency=session.get('Currency', {}),
        spells=session.get('Spells', {}),
        abilities=session.get('Abilities', {}),
        ac=session.get('AC', 10),
        spellslots=session.get('Spellslots', {}),
        movement_speed=session.get('Movement_Speed', 30),
        travel_end_time=session.get('Travel_End_Time', None),
        level=session.get('Level', 1),
        xp=session.get('XP', 0),
        reputation=session.get('Reputation', 0),
        faction=session.get('Faction', "Neutral"),
        relations=session.get('Relations', {}),
        max_hp=session.get('Max_HP', 1),
        curr_hp=session.get('Curr_HP', 1),
        current_area=starting_area,
        current_location=session.get('Current_Location') if session.get('Current_Location') else "Northhold",
        current_region=session.get('Current_Region') if session.get('Current_Region') else "Northern Mountains",
        current_continent=session.get('Current_Continent') if session.get('Current_Continent') else "Aetheria",
        current_world=session.get('Current_World') if session.get('Current_World') else "Eldoria",
    )

    return character


class InventoryView(discord.ui.View):
    def __init__(self, character):
        super().__init__(timeout=180)  # 3 minute timeout
        self.character = character
        self.current_page = 0
        self.items_per_page = 10
        self.current_category = "All"
        
        # Define categories
        self.categories = ["All", "Equipment", "Consumable", "Tool", "Weapon", "Armor", "Other"]
        
        # Add category select menu
        self.add_item(CategorySelect(self.categories))

        # Add navigation buttons
        self.prev_button = discord.ui.Button(
            label="◀", 
            custom_id="prev", 
            style=discord.ButtonStyle.grey,
            disabled=True  # Start with prev disabled on first page
        )
        self.next_button = discord.ui.Button(
            label="▶", 
            custom_id="next", 
            style=discord.ButtonStyle.grey,
            disabled=True  # Will be enabled if there are more pages
        )
        
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        
        # Update button states based on initial content
        self.update_button_states()

    def update_button_states(self):
        """Update navigation button states based on current page and total pages"""
        items = self.get_filtered_items()
        total_pages = max(1, math.ceil(len(items) / self.items_per_page))
        
        # Disable both buttons if there's only one page
        if total_pages <= 1:
            self.prev_button.disabled = True
            self.next_button.disabled = True
            return

        # Update button states based on current page
        self.prev_button.disabled = (self.current_page <= 0)
        self.next_button.disabled = (self.current_page >= total_pages - 1)

    @discord.ui.button(label="◀", custom_id="prev", style=discord.ButtonStyle.grey)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = self.get_filtered_items()
        total_pages = max(1, math.ceil(len(items) / self.items_per_page))
        
        if total_pages <= 1:
            # If there's only one page, acknowledge the interaction but don't change anything
            await interaction.response.defer()
            return
            
        if self.current_page > 0:
            self.current_page -= 1
            self.update_button_states()
            await interaction.response.edit_message(
                embed=self.get_page_embed(),
                view=self
            )
        else:
            # If we're already on the first page, just acknowledge the interaction
            await interaction.response.defer()

    @discord.ui.button(label="▶", custom_id="next", style=discord.ButtonStyle.grey)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = self.get_filtered_items()
        total_pages = max(1, math.ceil(len(items) / self.items_per_page))
        
        if total_pages <= 1:
            # If there's only one page, acknowledge the interaction but don't change anything
            await interaction.response.defer()
            return
            
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.update_button_states()
            await interaction.response.edit_message(
                embed=self.get_page_embed(),
                view=self
            )
        else:
            # If we're already on the last page, just acknowledge the interaction
            await interaction.response.defer()

    def get_filtered_items(self):
        """Get items for current category"""
        if self.current_category == "All":
            equipment_items = [(slot, item) for slot, item in self.character.equipment.items() 
                             if item is not None and not isinstance(item, list)]
            inventory_items = [(None, item) for item in self.character.inventory.values()]
            return equipment_items + inventory_items
            
        items = []
        # Add equipped items of matching category
        for slot, item in self.character.equipment.items():
            if not isinstance(item, list) and item is not None:
                if (hasattr(item, 'Type') and item.Type == self.current_category) or \
                   (isinstance(item, dict) and item.get('Type') == self.current_category):
                    items.append((slot, item))
        
        # Add inventory items of matching category
        for item in self.character.inventory.values():
            if (hasattr(item, 'Type') and item.Type == self.current_category) or \
               (isinstance(item, dict) and item.get('Type') == self.current_category):
                items.append((None, item))
        
        return items

    def get_page_embed(self):
        """Generate embed for current page and category"""
        items = self.get_filtered_items()
        total_pages = max(1, math.ceil(len(items) / self.items_per_page))
        
        embed = discord.Embed(
            title=f"{self.character.name}'s Equipment & Inventory",
            description=f"Category: **{self.current_category}** (Page {self.current_page + 1}/{total_pages})",
            color=discord.Color.blue()
        )

        start_idx = self.current_page * self.items_per_page
        page_items = items[start_idx:start_idx + self.items_per_page]

        if page_items:
            items_text = []
            for slot, item in page_items:
                if hasattr(item, 'Name') and hasattr(item, 'Type'):
                    if slot:
                        items_text.append(f"**{slot}**: {item.Name} ({item.Type})")
                    else:
                        items_text.append(f"- {item.Name} ({item.Type})")
                elif isinstance(item, dict):
                    if slot:
                        items_text.append(f"**{slot}**: {item.get('Name', 'Unknown')} ({item.get('Type', 'Unknown')})")
                    else:
                        items_text.append(f"- {item.get('Name', 'Unknown')} ({item.get('Type', 'Unknown')})")
            
            embed.add_field(
                name="Items",
                value='\n'.join(items_text),
                inline=False
            )
        else:
            embed.add_field(
                name="Items",
                value=f"No items in category: {self.current_category}",
                inline=False
            )

        # Add carrying capacity
        stats_text = (
            f"**Capacity**: {self.character.capacity} lbs\n"
            f"**Current Load**: {sum(item.Weight for item in self.character.inventory.values() if hasattr(item, 'Weight'))} lbs"
        )
        embed.add_field(name="Carrying Capacity", value=stats_text, inline=False)
        embed.set_footer(text="Use /examine <item> to view detailed information about specific items")
        
        return embed

class CategorySelect(discord.ui.Select):
    def __init__(self, categories):
        options = [
            discord.SelectOption(
                label=category,
                description=f"View {category.lower()} items"
            ) for category in categories
        ]
        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        view: InventoryView = self.view
        view.current_category = self.values[0]
        view.current_page = 0  # Reset to first page when changing categories
        view.update_button_states()  # Update button states for new category
        await interaction.response.edit_message(
            embed=view.get_page_embed(),
            view=view
        )

class SceneView(discord.ui.View):
    def __init__(self, character, current_view="general"):
        super().__init__(timeout=180)  # 3 minute timeout
        self.character = character
        self.current_view = current_view
        
        # Add view selection buttons
        self.add_item(ViewButton("General", "general", "🌍", discord.ButtonStyle.blurple))
        self.add_item(ViewButton("NPCs", "npcs", "👥", discord.ButtonStyle.blurple))
        self.add_item(ViewButton("Items", "items", "💎", discord.ButtonStyle.blurple))
        if character.current_area.connected_areas:
            self.add_item(ViewButton("Exits", "exits", "🚪", discord.ButtonStyle.blurple))

    def get_embed(self):
        """Generate the appropriate embed based on current view"""
        area = self.character.current_area
        
        if self.current_view == "general":
            embed = discord.Embed(
                title=f"📍 {area.name}",
                description=area.description,
                color=discord.Color.green()
            )
            
            # Quick overview sections
            if area.npcs:
                npc_list = ", ".join(f"**{npc.name}**" for npc in area.npcs)
                embed.add_field(
                    name="Present NPCs",
                    value=npc_list,
                    inline=False
                )
            
            if area.inventory:
                item_list = ", ".join(f"**{item.Name}**" for item in area.inventory if hasattr(item, 'Name'))
                embed.add_field(
                    name="Visible Items",
                    value=item_list if item_list else "None",
                    inline=False
                )
            
            if area.connected_areas:
                exits = ", ".join(f"**{connected.name}**" for connected in area.connected_areas)
                embed.add_field(
                    name="Exits",
                    value=exits,
                    inline=False
                )
            
        elif self.current_view == "npcs":
            embed = discord.Embed(
                title=f"👥 People in {area.name}",
                color=discord.Color.blue()
            )
            
            if area.npcs:
                for npc in area.npcs:
                    # Create detailed NPC description
                    npc_details = []
                    if hasattr(npc, 'description'):
                        npc_details.append(npc.description)
                    if hasattr(npc, 'attitude'):
                        npc_details.append(f"*{npc.attitude}*")
                        
                    embed.add_field(
                        name=npc.name,
                        value="\n".join(npc_details) if npc_details else "A mysterious figure.",
                        inline=False
                    )
            else:
                embed.description = "There is no one else here."
            
        elif self.current_view == "items":
            embed = discord.Embed(
                title=f"💎 Items in {area.name}",
                color=discord.Color.gold()
            )
            
            if area.inventory:
                for item in area.inventory:
                    if hasattr(item, 'Name') and hasattr(item, 'Description'):
                        embed.add_field(
                            name=item.Name,
                            value=item.Description[:100] + "..." if len(item.Description) > 100 else item.Description,
                            inline=False
                        )
            else:
                embed.description = "There are no items of note here."
            
        elif self.current_view == "exits":
            embed = discord.Embed(
                title=f"🚪 Exits from {area.name}",
                color=discord.Color.purple()
            )
            
            if area.connected_areas:
                for connected in area.connected_areas:
                    # You might want to add more details about each exit
                    # like distance, difficulty, or special requirements
                    embed.add_field(
                        name=connected.name,
                        value=connected.description[:100] + "..." if len(connected.description) > 100 else connected.description,
                        inline=False
                    )
            else:
                embed.description = "There appear to be no exits from this area."
        
        # Add footer with helpful command hints based on current view
        if self.current_view == "npcs":
            embed.set_footer(text="Use /talk <name> to interact with NPCs")
        elif self.current_view == "items":
            embed.set_footer(text="Use /pickup <item> to collect items • /examine <item> for details")
        elif self.current_view == "exits":
            embed.set_footer(text="Use /travel <location> to move to a new area")
        else:
            embed.set_footer(text="Click the buttons above to focus on specific aspects of the area")
            
        return embed

class ViewButton(discord.ui.Button):
    def __init__(self, label, view_type, emoji, style):
        super().__init__(label=label, emoji=emoji, style=style)
        self.view_type = view_type

    async def callback(self, interaction: discord.Interaction):
        view: SceneView = self.view
        view.current_view = self.view_type
        
        # Update button styles
        for item in view.children:
            if isinstance(item, ViewButton):
                item.style = (
                    discord.ButtonStyle.green 
                    if item.view_type == self.view_type 
                    else discord.ButtonStyle.blurple
                )
        
        await interaction.response.edit_message(
            embed=view.get_embed(),
            view=view
        )

# ---------------------------- #
#          Helper Functions    #
# ---------------------------- #
def load_or_get_character(user_id: str, force_reload: bool = False):
    global character_cache, last_cache_update, characters
    
    # Clean the input user_id
    user_id = clean_user_id(user_id)
    logging.info(f"Looking for cleaned user_id: {user_id}")
    
    current_time = time.time()
    
    try:
        if (force_reload or 
            not character_cache or 
            (current_time - last_cache_update) >= CACHE_DURATION):
            
            logging.info("Reloading character cache from file")
            
            try:
                with open('characters.json', 'r', encoding='utf-8') as f:
                    char_data = json.load(f)
                
                # Convert the loaded data into Character objects
                characters = {}
                for uid, data in char_data.items():
                    uid = str(uid)  # Ensure key is string
                    try:
                        logging.debug(f"Creating character for {uid} with data: {data}")
                        character_obj = Character.from_dict(
                            data=data,
                            user_id=uid,
                            area_lookup=area_lookup,
                            item_lookup=items
                        )
                        if character_obj:
                            characters[uid] = character_obj
                            logging.debug(f"Successfully created character for {uid}")
                    except Exception as e:
                        logging.error(f"Error creating character for {uid}: {e}")
                        continue
                
                # Update cache
                character_cache = characters.copy()
                last_cache_update = current_time
                
                logging.info(f"Successfully loaded {len(characters)} characters. Available IDs: {list(characters.keys())}")
                
            except FileNotFoundError:
                logging.warning("characters.json not found - creating new file")
                characters = {}
                character_cache = {}
                with open('characters.json', 'w', encoding='utf-8') as f:
                    json.dump({}, f)
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding characters.json: {e}")
                return None
        
        # Get character from cache
        character = character_cache.get(user_id)
        if character:
            logging.info(f"Found character {character.name} for user {user_id}")
            return character
        
        logging.info(f"No character found for user {user_id} in cache")
        return None
        
    except Exception as e:
        logging.error(f"Error loading character for user {user_id}: {e}", exc_info=True)
        return None

    

def format_duration(seconds):
    """Format seconds into a readable string"""
    # Convert to int if it's a float
    seconds = int(seconds)
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 and not hours:  # Only show seconds if less than an hour
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    return " ".join(parts)

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
    global actions
    actions = actions
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
    
def create_progress_bar(current: int, maximum: int, length: int = 10) -> str:
    """
    Creates a visual progress bar using block characters.
    Args:
        current (int): Current value
        maximum (int): Maximum value
        length (int): Length of the progress bar in characters
    Returns:
        str: A string representing a progress bar
    """
    try:
        if maximum <= 0:
            return "⬜" * length
        
        filled = int((current / maximum) * length)
        if filled > length:
            filled = length
        elif filled < 0:
            filled = 0
            
        empty = length - filled
        
        # Using different Unicode block characters for better visualization
        bar = "⬛" * filled + "⬜" * empty
        
        # Add percentage
        percentage = int((current / maximum) * 100)
        return f"{bar} {percentage}%"
    except Exception as e:
        logging.error(f"Error creating progress bar: {e}")
        return "Error"
 

# ---------------------------- #
#          Command Tree        #
# ---------------------------- #

@bot.tree.command(name="sync", description="Manually sync bot commands")
@commands.has_permissions(administrator=True)
async def sync(interaction: discord.Interaction):
    """Manual command to sync commands to the current guild"""
    try:
        if interaction.guild_id not in GUILD_CONFIGS:
            await interaction.response.send_message(
                "This guild is not configured for command syncing.",
                ephemeral=True
            )
            return

        guild = discord.Object(id=interaction.guild_id)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        
        await interaction.response.send_message(
            f"Successfully synced {len(synced)} commands to this guild!",
            ephemeral=True
        )
        logging.info(f"Manually synced commands to guild {interaction.guild_id}")
        
    except Exception as e:
        logging.error(f"Error in manual sync command: {e}")
        await interaction.response.send_message(
            "Failed to sync commands.",
            ephemeral=True
        )

@bot.tree.command(name="create_character", description="Create a new character")
async def create_character(interaction: discord.Interaction):
    global character_creation_sessions
    try:
        # Respond to the interaction first
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Initialize character creation session
            user_id = str(interaction.user.id)
            if character_creation_sessions is None:
                character_creation_sessions = {}
            character_creation_sessions[user_id] = {'Stats': {}, 'points_spent': 0}
            
            # Send DM with character creation view
            await interaction.user.send(
                "Let's create your character!", 
                view=CharacterCreationView(bot)
            )
            
            # Follow up to the original interaction
            await interaction.followup.send(
                "Check your DMs to start character creation!",
                ephemeral=True
            )
            
            logging.info(f"User {interaction.user.id} initiated character creation.")
            
        except discord.Forbidden:
            await interaction.followup.send(
                "Unable to send you a DM. Please check your privacy settings.",
                ephemeral=True
            )
            
    except Exception as e:
        logging.error(f"Error in create_character: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "An error occurred while creating your character.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "An error occurred while creating your character.",
                ephemeral=True
            )

@bot.tree.command(name="attack", description="Attack an NPC in your current area.")
@app_commands.describe(npc_name="The name of the NPC to attack.")
async def attack(interaction: discord.Interaction, npc_name: str):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )

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

@bot.tree.command(name="npc_list", description="List all NPCs in your current area.")
async def npc_list(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )

    area = character.current_area
    if area.npcs:
        npc_names = ', '.join(npc.name for npc in area.npcs)
        await interaction.response.send_message(f"NPCs in **{area.name}**: {npc_names}", ephemeral=False)
    else:
        await interaction.response.send_message(f"There are no NPCs in **{area.name}**.", ephemeral=False)

@bot.tree.command(name="talk", description="Talk to an NPC in your current area.")
@app_commands.describe(npc_name="The name of the NPC to talk to.")
async def talk(interaction: discord.Interaction, npc_name: str):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )

    area = character.current_area
    for npc in area.npcs:
        if npc.name.lower() == npc_name.lower():
            # For simplicity, send the first dialogue line
            dialogue = npc.get_dialogue if npc.dialogue else f"{npc.name} has nothing to say."
            await interaction.response.send_message(f"**{npc.name}** says: \"{dialogue}\"", ephemeral=False)
            return

    await interaction.response.send_message(f"**{npc_name}** is not in **{area.name}**.", ephemeral=True)

class InventoryView(discord.ui.View):
    def __init__(self, character):
        super().__init__(timeout=180)  # 3 minute timeout
        self.character = character
        self.current_page = 0
        self.items_per_page = 10
        self.current_category = "All"
        
        # Define categories
        self.categories = ["All", "Equipment", "Consumable", "Tool", "Weapon", "Armor", "Other"]
        
        # Add category select menu
        self.add_item(CategorySelect(self.categories))
        
        # Add navigation buttons
        self.add_item(discord.ui.Button(label="◀", custom_id="prev", style=discord.ButtonStyle.grey))
        self.add_item(discord.ui.Button(label="▶", custom_id="next", style=discord.ButtonStyle.grey))

    def get_filtered_items(self):
        """Get items for current category"""
        if self.current_category == "All":
            equipment_items = [(slot, item) for slot, item in self.character.equipment.items() 
                             if item is not None and not isinstance(item, list)]
            inventory_items = [(None, item) for item in self.character.inventory.values()]
            return equipment_items + inventory_items
            
        items = []
        # Add equipped items of matching category
        for slot, item in self.character.equipment.items():
            if not isinstance(item, list) and item is not None:
                if (hasattr(item, 'Type') and item.Type == self.current_category) or \
                   (isinstance(item, dict) and item.get('Type') == self.current_category):
                    items.append((slot, item))
        
        # Add inventory items of matching category
        for item in self.character.inventory.values():
            if (hasattr(item, 'Type') and item.Type == self.current_category) or \
               (isinstance(item, dict) and item.get('Type') == self.current_category):
                items.append((None, item))
        
        return items

    def get_page_embed(self):
        """Generate embed for current page and category"""
        items = self.get_filtered_items()
        total_pages = max(1, math.ceil(len(items) / self.items_per_page))
        
        embed = discord.Embed(
            title=f"{self.character.name}'s Equipment & Inventory",
            description=f"Category: **{self.current_category}** (Page {self.current_page + 1}/{total_pages})",
            color=discord.Color.blue()
        )

        start_idx = self.current_page * self.items_per_page
        page_items = items[start_idx:start_idx + self.items_per_page]

        if page_items:
            items_text = []
            for slot, item in page_items:
                if hasattr(item, 'Name') and hasattr(item, 'Type'):
                    if slot:
                        items_text.append(f"**{slot}**: {item.Name} ({item.Type})")
                    else:
                        items_text.append(f"- {item.Name} ({item.Type})")
                elif isinstance(item, dict):
                    if slot:
                        items_text.append(f"**{slot}**: {item.get('Name', 'Unknown')} ({item.get('Type', 'Unknown')})")
                    else:
                        items_text.append(f"- {item.get('Name', 'Unknown')} ({item.get('Type', 'Unknown')})")
            
            embed.add_field(
                name="Items",
                value='\n'.join(items_text),
                inline=False
            )
        else:
            embed.add_field(
                name="Items",
                value=f"No items in category: {self.current_category}",
                inline=False
            )

        # Add carrying capacity
        stats_text = (
            f"**Capacity**: {self.character.capacity} lbs\n"
            f"**Current Load**: {sum(item.Weight for item in self.character.inventory.values() if hasattr(item, 'Weight'))} lbs"
        )
        embed.add_field(name="Carrying Capacity", value=stats_text, inline=False)
        embed.set_footer(text="Use /examine <item> to view detailed information about specific items")
        
        return embed

class CategorySelect(discord.ui.Select):
    def __init__(self, categories):
        options = [
            discord.SelectOption(
                label=category,
                description=f"View {category.lower()} items"
            ) for category in categories
        ]
        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        view: InventoryView = self.view
        view.current_category = self.values[0]
        view.current_page = 0  # Reset to first page when changing categories
        await interaction.response.edit_message(embed=view.get_page_embed(), view=view)


@bot.tree.command(name="pickup", description="Pick up an item from the area.")
@app_commands.describe(item_name="The name of the item to pick up.")
async def pickup(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
    channel_id = get_guild_game_channel(character.last_interaction_guild)
        
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )
   
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

@bot.tree.command(name="drop", description="Drop an item from your inventory into the area.")
@app_commands.describe(item_name="The name of the item to drop.")
async def drop(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
    channel_id = get_guild_game_channel(character.last_interaction_guild)
        
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )

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

@bot.tree.command(name="destroy", description="Destroy an item in your inventory.")
@app_commands.describe(item_name="The name of the item to destroy.")
async def destroy(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )

    # Find the item in the character's inventory
    for item in character.inventory:
        if item.name.lower() == item_name.lower():
            character.remove_item_from_inventory(item.name)
            save_characters(characters)
            await interaction.response.send_message(f"You have destroyed **{item.name}**.", ephemeral=False)
            return

    await interaction.response.send_message(f"You don't have an item named **{item_name}**.", ephemeral=True)

@bot.tree.command(name="equip", description="Equip an item from your inventory.")
@app_commands.describe(item_name="The name of the item to equip.", slot="The equipment slot.")
async def equip(interaction: discord.Interaction, item_name: str, slot: str):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )

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

@bot.tree.command(name="unequip", description="Unequip an item from a slot back to your inventory.")
@app_commands.describe(slot="The equipment slot to unequip.")
async def unequip(interaction: discord.Interaction, slot: str):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )

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

@bot.tree.command(name="use", description="Use a consumable item from your inventory.")
@app_commands.describe(item_name="The name of the item to use.")
async def use_item(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)

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

@bot.tree.command(name="examine", description="Examine an item in your inventory or equipment.")
@app_commands.describe(item_name="The name of the item to examine.")
async def examine(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )

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

@bot.tree.command(name="identify", description="Identify a magical item in your inventory.")
@app_commands.describe(item_name="The name of the item to identify.")
async def identify(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
    
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )

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

@bot.tree.command(name="travel", description="Move to a connected area.")
@app_commands.describe(destination="The name of the area to move to.")
async def travel(interaction: discord.Interaction, destination: str):
    try:
        user_id = str(interaction.user.id)
        character = load_or_get_character(user_id)
        
        if not character:
            await interaction.response.send_message(
                "You don't have a character yet. Use `/create_character` to get started.",
                ephemeral=True
            )
            return

        # Store the guild ID where the command was used
        character.last_interaction_guild = interaction.guild_id

        # Check if already traveling
        current_time = time.time()
        if character.is_traveling and character.travel_end_time:
            remaining_time = character.travel_end_time - current_time
            if remaining_time > 0:
                await interaction.response.send_message(
                    f"You are already traveling! You will arrive at your destination in {format_duration(remaining_time)}.",
                    ephemeral=True
                )
                return

        # Validate destination
        destination_area = area_lookup.get(destination)
        if not destination_area:
            await interaction.response.send_message(
                f"Destination '{destination}' does not exist.",
                ephemeral=True
            )
            return

        # Check if destination is current location
        if character.current_area and character.current_area.name == destination:
            await interaction.response.send_message(
                "You are already at that location!",
                ephemeral=True
            )
            return

        # Check if destination is connected to current area
        if character.current_area and destination_area not in character.current_area.connected_areas:
            await interaction.response.send_message(
                f"You cannot travel directly to {destination}. You must travel through connected areas.",
                ephemeral=True
            )
            return

        # Calculate travel details
        travel_duration = get_travel_time(character, destination_area)
        current_time = time.time()
        character.travel_end_time = current_time + travel_duration

        #create embed
        embed = discord.Embed(
        title="🚶 Travel Initiated",
        description=f"Traveling from **{character.current_area.name}** to **{destination}**",
        color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Estimated Travel Time",
            value=format_duration(travel_duration),
            inline=True
        )
        embed.add_field(

            name="Expected Arrival",
            value=f"<t:{int(character.travel_end_time)}:R>",  # Discord timestamp format
            inline=True
        )
        
        # Add distance if available
        if hasattr(character.current_area, 'coordinates') and hasattr(destination_area, 'coordinates'):
            distance = calculate_distance(character.current_area.coordinates, destination_area.coordinates)
            embed.add_field(
                name="Distance",
                value=f"{distance:.1f} units",
                inline=True
            )

        # Add route information if available
        if hasattr(destination_area, 'description'):
            embed.add_field(
                name="Destination Description",
                value=destination_area.description[:200] + "..." if len(destination_area.description) > 200 else destination_area.description,
                inline=False
            )

        # Add warnings or notes
        if hasattr(destination_area, 'danger_level'):
            embed.add_field(
                name="⚠️ Warning",
                value=f"This area has a danger level of {destination_area.danger_level}",
                inline=False
            )

        # Set travel state
        character.is_traveling = True
        character.travel_destination = destination_area
        
        characters[user_id] = character
        save_characters(characters)

        # Acknowledge the command in the channel
        await interaction.response.send_message(
            "Travel initiated! Check your DMs for travel details.",
            ephemeral=True
        )

        # Send the travel embed as DM and store the message reference
        try:
            travel_message = await interaction.user.send(embed=embed)
            # Store the message reference in character data
            character.last_travel_message = travel_message
            characters[user_id] = character
            save_characters(characters)
            
            logging.info(f"Travel details sent to user {user_id} via DM")
        except discord.Forbidden:
            await interaction.followup.send(
                "Couldn't send travel details via DM. Here are your travel details:",
                embed=embed,
                ephemeral=True
            )
            logging.warning(f"Couldn't send DM to user {user_id}, sent travel details in channel instead")
        except Exception as e:
            logging.error(f"Error sending travel details to user {user_id}: {e}")
            await interaction.followup.send(
                "An error occurred while sending travel details.",
                ephemeral=True
            )

        logging.info(f"User '{user_id}' started traveling to '{destination}'.")
       
        # Start the travel task
        asyncio.create_task(travel_task(bot, character, user_id, characters, save_characters))
        
    except Exception as e:
        logging.error(f"Error in travel command: {e}")
        await interaction.response.send_message(
            "An error occurred while processing your travel request.",
            ephemeral=True
        )

# Travel command autocomplete
@travel.autocomplete('destination')
async def travel_autocomplete(interaction: discord.Interaction, current: str):
    try:
        user_id = str(interaction.user.id)
        character = load_or_get_character(user_id)

        if not character or not character.current_area:
            return []

        connected_areas = character.current_area.connected_areas
        
        # If user hasn't typed anything yet, show all connected areas
        if not current:
            suggestions = [
                app_commands.Choice(
                    name=f"{area.name} - {area.description[:50]}..." if area.description else area.name,
                    value=area.name
                )
                for area in connected_areas
            ]
        else:
            # Filter based on current input (case-insensitive)
            suggestions = [
                app_commands.Choice(
                    name=f"{area.name} - {area.description[:50]}..." if area.description else area.name,
                    value=area.name
                )
                for area in connected_areas
                if current.lower() in area.name.lower()
            ]

        # Discord limits to 25 choices
        return suggestions[:25]
    except Exception as e:
        logging.error(f"Error in travel autocomplete: {e}")
        return []


@bot.tree.command(name="travel_location", description="Travel to a different location within your current region.")
@app_commands.describe(location_name="The name of the location to travel to.")
async def travel_location(interaction: discord.Interaction, location_name: str):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )

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

@bot.tree.command(name="rest", description="Rest to regain health and spell slots.")
async def rest(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
        
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )


    character.rest()
    save_characters(characters)
    await interaction.response.send_message("You have rested and regained health and spell slots.", ephemeral=False)

@bot.tree.command(name="location", description="View your current location.")
async def location(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)

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
        "in the region of f **{region}**, on the continent of **{continent}**, on the planet **{world}**."
    )

    await interaction.response.send_message(
        response_message,
        ephemeral=False
    )

@bot.tree.command(name="scene", description="View your current surroundings")
async def scene(interaction: discord.Interaction):
    try:
        user_id = str(interaction.user.id)
        character = load_or_get_character(user_id)
        
        if not character:
            await interaction.response.send_message(
                "You don't have a character yet. Use `/create_character` to get started.",
                ephemeral=True
            )
            return

        if not character.current_area:
            await interaction.response.send_message(
                "You seem to be... nowhere? Please contact an administrator.",
                ephemeral=True
            )
            return

        # Create the view and initial embed
        view = SceneView(character)
        embed = view.get_embed()
        
        # Send the interactive scene description
        await interaction.response.send_message(embed=embed, view=view)
        logging.info(f"Scene information sent for user {user_id} in area {character.current_area.name}")

    except Exception as e:
        logging.error(f"Error in scene command: {e}", exc_info=True)
        await interaction.response.send_message(
            "An error occurred while displaying the scene. Please try again.",
            ephemeral=True
        )

@bot.tree.command(name="stats", description="View your character's complete stats and abilities")
async def stats(interaction: discord.Interaction):
    try:
        user_id = str(interaction.user.id)
        debug_cache_state()
        character = load_or_get_character(user_id)
        debug_cache_state()
        
        if not character:
            await interaction.response.send_message(
                "You don't have a character yet. Use `/create_character` to get started.",
                ephemeral=True
            )
            return

        # Create the main character sheet embed
        embed = discord.Embed(
            title=f"{character.name}'s Character Sheet",
            description=f"Level {character.level} {character.species} {character.char_class}",
            color=discord.Color.blue()
        )

        # Add character thumbnail if implemented
        # embed.set_thumbnail(url="character_avatar_url")

        # Basic Info Field
        basic_info = (
            f"**Gender:** {character.gender}\n"
            f"**Pronouns:** {character.pronouns}\n"
            f"**XP:** {character.xp}"
        )
        embed.add_field(name="Basic Info", value=basic_info, inline=False)

        # Health and Defense
        hp_bar = create_progress_bar(character.curr_hp, character.max_hp)
        defense_info = (
            f"**HP:** {character.curr_hp}/{character.max_hp} {hp_bar}\n"
            f"**AC:** {character.ac}\n"
            f"**Movement Speed:** {character.movement_speed} ft"
        )
        embed.add_field(name="Health & Defense", value=defense_info, inline=False)

        # Core Stats with Modifiers
        stats_info = ""
        for stat, value in character.stats.items():
            modifier = character.get_stat_modifier(stat)
            sign = "+" if modifier >= 0 else ""
            stats_info += f"**{stat}:** {value} ({sign}{modifier})\n"
        embed.add_field(name="Ability Scores", value=stats_info, inline=True)

        # Skills
        if character.skills:
            skills_info = "\n".join(f"**{skill}:** {value}" for skill, value in character.skills.items())
            embed.add_field(name="Skills", value=skills_info or "None", inline=True)

        # Equipment
        equipment_info = []
        if character.equipment:
            # Handle regular equipment slots
            for slot in ['Armor', 'Left_Hand', 'Right_Hand', 'Back']:
                item = character.equipment.get(slot)
                if item and hasattr(item, 'Name'):
                    equipment_info.append(f"**{slot}:** {item.Name}")
                else:
                    equipment_info.append(f"**{slot}:** Empty")
            
            # Handle Belt Slots
            belt_items = []
            for i, item in enumerate(character.equipment.get('Belt_Slots', [])):
                if item and hasattr(item, 'Name'):
                    belt_items.append(f"Slot {i+1}: {item.Name}")
            if belt_items:
                equipment_info.append("**Belt Slots:**\n" + "\n".join(belt_items))
            else:
                equipment_info.append("**Belt Slots:** Empty")
            
            # Handle Magic Slots
            magic_items = []
            for i, item in enumerate(character.equipment.get('Magic_Slots', [])):
                if item and hasattr(item, 'Name'):
                    magic_items.append(f"Slot {i+1}: {item.Name}")
            if magic_items:
                equipment_info.append("**Magic Slots:**\n" + "\n".join(magic_items))
            else:
                equipment_info.append("**Magic Slots:** Empty")

        embed.add_field(
            name="Equipment",
            value="\n".join(equipment_info) if equipment_info else "No equipment",
            inline=False
        )

        # Spells and Spell Slots
        if character.spells or character.spellslots:
            spells_info = "**Spell Slots:**\n"
            if character.spellslots:
                for level, slots in character.spellslots.items():
                    if isinstance(slots, dict):
                        available = slots.get('available', 0)
                        maximum = slots.get('max', 0)
                        slot_bar = create_progress_bar(available, maximum)
                        spells_info += f"Level {level}: {available}/{maximum} {slot_bar}\n"
            
            if character.spells:
                spells_info += "\n**Known Spells:**\n"
                for level, spells in character.spells.items():
                    spell_list = ", ".join(spells) if isinstance(spells, list) else spells
                    spells_info += f"Level {level}: {spell_list}\n"
            
            embed.add_field(name="Spellcasting", value=spells_info or "No spells", inline=False)

        # Abilities
        if character.abilities:
            abilities_info = "\n".join(f"**{ability}:** {desc}" 
                                     for ability, desc in character.abilities.items())
            embed.add_field(name="Abilities", value=abilities_info or "No abilities", inline=False)

        # Currency
        if character.currency:
            currency_info = "\n".join(f"**{currency}:** {amount}" 
                                    for currency, amount in character.currency.items())
            embed.add_field(name="Currency", value=currency_info or "No currency", inline=True)

        # Add footer with character creation date or last updated
        embed.set_footer(text="Use /scene to view your surroundings")

        try:
            # Send the embed as a DM
            await interaction.user.send(embed=embed)
            # Acknowledge the command in the channel
            await interaction.response.send_message(
                "I've sent your character sheet to your DMs!", 
                ephemeral=True
            )
        except discord.Forbidden:
            # If DMs are disabled
            await interaction.response.send_message(
                "I couldn't send you a DM. Please check your privacy settings.", 
                ephemeral=True
            )
        except Exception as e:
            logging.error(f"Error sending character sheet DM: {e}")
            await interaction.response.send_message(
                "An error occurred while sending your character sheet.", 
                ephemeral=True
            )

    except Exception as e:
        logging.error(f"Error displaying character sheet: {e}", exc_info=True)
        await interaction.response.send_message(
            "An error occurred while displaying your character sheet. Please try again.",
            ephemeral=True
        )

@bot.tree.command(
    name="inventory",
    description="View your character's inventory and equipment"
)
async def inventory_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    character = load_or_get_character(user_id)
   
    if not character:
        await interaction.response.send_message(
            "You don't have a character yet. Use `/create_character` to get started.",
            ephemeral=True
        )
        return

    view = InventoryView(character)
    try:
        # Send the initial embed with view as a DM
        await interaction.user.send(embed=view.get_page_embed(), view=view)
        # Acknowledge the command in the channel
        await interaction.response.send_message(
            "I've sent your inventory details to your DMs!", 
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I couldn't send you a DM. Please check your privacy settings.", 
            ephemeral=True
        )
    except Exception as e:
        logging.error(f"Error sending inventory DM: {e}")
        await interaction.response.send_message(
            "An error occurred while sending your inventory details.", 
            ephemeral=True
        )

# Add button callbacks to InventoryView
@discord.ui.button(label="◀", custom_id="prev", style=discord.ButtonStyle.grey)
async def prev_page(self, button: discord.ui.Button, interaction: discord.Interaction):
    items = self.get_filtered_items()
    total_pages = max(1, math.ceil(len(items) / self.items_per_page))
    self.current_page = (self.current_page - 1) % total_pages
    await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

@discord.ui.button(label="▶", custom_id="next", style=discord.ButtonStyle.grey)
async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
    items = self.get_filtered_items()
    total_pages = max(1, math.ceil(len(items) / self.items_per_page))
    self.current_page = (self.current_page + 1) % total_pages
    await interaction.response.edit_message(embed=self.get_page_embed(), view=self)



# ---------------------------- #
#           Events             #
# ---------------------------- #

async def update_world_state():
    """Update dynamic aspects of the world periodically"""
    try:
        # Update NPC positions
        await update_npc_locations()
        
        # Update available items in areas
        await update_area_inventories()
        
        # Update NPC states (like health, inventory, etc.)
        await update_npc_states()
        
        # Save current world state
        save_world_state()
        
    except Exception as e:
        logging.error(f"Error updating world state: {e}")

async def update_npc_locations():
    """Move NPCs between areas based on their schedules and behaviors"""
    try:
        for npc in npcs.values():
            if random.random() < 0.1:  # 10% chance to move
                current_area = npc.current_area
                if current_area and current_area.connected_areas:
                    new_area = random.choice(current_area.connected_areas)
                    # Remove NPC from current area
                    current_area.npcs.remove(npc)
                    # Add NPC to new area
                    new_area.npcs.append(npc)
                    npc.current_area = new_area
                    logging.info(f"NPC {npc.Name} moved from {current_area.name} to {new_area.name}")
    except Exception as e:
        logging.error(f"Error updating NPC locations: {e}")

async def update_area_inventories():
    """Update item spawns and removals in areas"""
    try:
        for area in area_lookup.values():
            # Chance to spawn new items
            if random.random() < 0.05:  # 5% chance
                new_item = generate_random_item()
                area.inventory.append(new_item)
                logging.info(f"New item {new_item.Name} spawned in {area.name}")
            
            # Chance to remove old items
            if area.inventory and random.random() < 0.05:
                removed_item = random.choice(area.inventory)
                area.inventory.remove(removed_item)
                logging.info(f"Item {removed_item.Name} removed from {area.name}")
    except Exception as e:
        logging.error(f"Error updating area inventories: {e}")

async def update_npc_states():
    """Update NPC states, behaviors, and inventories"""
    try:
        for npc in npcs.values():
            # Update NPC health regeneration
            if npc.curr_hp < npc.max_hp:
                npc.curr_hp = min(npc.max_hp, npc.curr_hp + 1)
            
            # Update NPC inventory
            if random.random() < 0.1:  # 10% chance
                if len(npc.inventory) > 0:
                    # Maybe trade or drop items
                    pass
                else:
                    # Maybe acquire new items
                    pass
            
            # Update NPC attitude/relationships
            for other_npc in npcs.values():
                if other_npc != npc and random.random() < 0.01:  # 1% chance
                    # Modify relationships based on proximity, events, etc.
                    pass
    except Exception as e:
        logging.error(f"Error updating NPC states: {e}")

def save_world_state():
    """Save the current state of the dynamic world"""
    try:
        # Save current NPC states
        save_npcs(npcs)
        
        # Save current area states
        save_areas(area_lookup)
        
        logging.info("World state saved successfully")
    except Exception as e:
        logging.error(f"Error saving world state: {e}")

async def sync_commands():
    """
    Synchronize commands to all configured guilds
    """
    try:
        successful_syncs = 0
        total_guilds = len(GUILD_CONFIGS)
        
        for guild_id in GUILD_CONFIGS:
            try:
                guild = discord.Object(id=guild_id)
                
                # Copy global commands to guild and sync
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                
                successful_syncs += 1
                logging.info(f"Successfully synced {len(synced)} commands to guild {guild_id}")
                
            except discord.Forbidden:
                logging.error(f"Missing permissions to sync commands in guild {guild_id}")
            except discord.HTTPException as e:
                logging.error(f"HTTP error syncing commands to guild {guild_id}: {e}")
            except Exception as e:
                logging.error(f"Error syncing commands to guild {guild_id}: {e}")

        if successful_syncs == total_guilds:
            logging.info(f"Successfully synced commands to all {total_guilds} guilds")
        else:
            logging.warning(f"Synced commands to {successful_syncs}/{total_guilds} guilds")

    except Exception as e:
        logging.error(f"Error in sync_commands: {e}", exc_info=True)

@bot.event
async def on_ready():
    try:
        logging.info(f'Logged in as {bot.user.name}')
        verify_character_data()
        # Start the scheduler
        if not hasattr(bot, 'scheduler_running'):
            scheduler = AsyncIOScheduler()
            scheduler.add_job(update_world_state, 'interval', minutes=5)
            scheduler.start()
            bot.scheduler_running = True
        
        # Verify guild configurations
        verify_guild_configs()
        
        # Sync commands to all guilds
        await sync_commands()
        
    except Exception as e:
        logging.error(f"Error in on_ready: {e}", exc_info=True)


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
        characters[user_id] = Character(user_id=user_id, name=message.author.name)
        save_characters(characters)
        await message.channel.send(f'Character created for {message.author.name}.')
        logging.info(f"Character created for user {user_id} with name {message.author.name}.")

    character = load_or_get_character(user_id)
   
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


@bot.event
async def on_shutdown():
    save_characters(characters)
    logging.info("Bot is shutting down. Character data saved.")
        

# ---------------------------- #
#         Running the Bot      #
# ---------------------------- #


if __name__ == "__main__":
    if initialize_game_data():
        bot.run(DISCORD_BOT_TOKEN)
    else:
        logging.error("Failed to initialize game data. Bot startup aborted.")
else:
    logging.error("Failed to register commands. Bot startup aborted.")

