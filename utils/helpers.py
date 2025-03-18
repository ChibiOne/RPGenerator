# utils/helpers.py
import logging
import random
import re
import pickle
from typing import Optional, Tuple, Any, List
import discord
from .redis_manager import ShardAwareRedisDB

class CharacterLoader:
    """Handles character loading and caching"""
    def __init__(self, bot):
        self.bot = bot
        self.character_cache = {}
        self.cache_duration = 300  # 5 minutes

    @staticmethod
    def clean_user_id(user_id: str) -> str:
        """Clean user ID input"""
        return str(user_id).strip()

    async def load_or_get_character_redis(self, user_id: str, guild_id: str, 
                                        force_reload: bool = False) -> Optional['Character']:
        """Redis version of load_or_get_character with caching"""
        try:
            user_id = self.clean_user_id(user_id)
            logging.info(f"Looking for user_id: {user_id} in guild: {guild_id}")

            if not force_reload and user_id in self.character_cache:
                return self.character_cache[user_id]

            key = f"character:{guild_id}:{user_id}"
            data = await self.bot.redis_player.get(key)
            
            if data:
                char_data = pickle.loads(data)
                character = Character.from_dict(
                    data=char_data,
                    user_id=user_id,
                    area_lookup=area_lookup,
                    item_lookup=items
                )
                
                if character:
                    self.character_cache[user_id] = character
                    logging.info(f"Loaded character {character.name} for user {user_id}")
                    return character

            logging.info(f"No character found for user {user_id}")
            return None

        except Exception as e:
            logging.error(f"Error loading character for user {user_id}: {e}", exc_info=True)
            return None

class TimeFormatter:
    """Handles time and duration formatting"""
    @staticmethod
    def format_duration(seconds: int) -> str:
        """Format seconds into a readable string"""
        seconds = int(seconds)
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0 and not hours:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        
        return " ".join(parts)

class GameMechanics:
    """Handles game mechanics and checks"""
    @staticmethod
    def perform_ability_check(character: 'Character', stat: str) -> Tuple[Optional[int], Optional[int]]:
        """Performs an ability check"""
        try:
            modifier = character.get_stat_modifier(stat)
            roll = random.randint(1, 20)
            total = roll + modifier
            logging.info(f"Ability check for {character.name}: {roll} + {modifier} = {total}")
            return roll, total
        except Exception as e:
            logging.error(f"Error in ability check for {character.name}: {e}")
            return None, None

class ActionParser:
    """Handles parsing and processing of game actions"""
    def __init__(self, actions_data: dict):
        self.actions = actions_data

    async def parse_action(self, message: discord.Message) -> Tuple[Optional[str], Optional[str]]:
        """Parses message for actions prefixed with '?'"""
        message_content = message.content.lower()
        logging.info(f"Parsing message from {message.author.id}: '{message_content}'")

        pattern = r'(?<!\w)\?[A-Za-z]+(?!\w)'
        matches = re.findall(pattern, message_content)

        if len(matches) > 1:
            logging.warning(f"Multiple actions detected: {matches}")
            await message.channel.send("Please specify only one action at a time.")
            return None, None

        for match in matches:
            action = match.lstrip('?')
            if action in self.actions:
                return action, self.actions[action]

        await self.show_actions(message)
        return None, None

    async def show_actions(self, message: discord.Message):
        """Shows available actions"""
        if self.actions:
            action_list = ', '.join(self.actions.keys())
            await message.channel.send(
                f"Sorry, I don't recognize that action. Available actions: {action_list}"
            )
        else:
            await message.channel.send("No actions are currently recognized.")

class GPTResponseHandler:
    """Handles interactions with GPT API"""
    def __init__(self, openai_client):
        self.client = openai_client

    async def get_response(self, prompt: str, channel_messages: List[str], 
                          stat: str, total: int, roll: int, 
                          character: 'Character', include_roll_info: bool = True) -> str:
        """Gets response from GPT-4"""
        try:
            messages = [
                {
                    "role": "system", 
                    "content": "You are a game master for a fantasy role-playing game. "
                              "Your job is to narrate the settings the players journey through, "
                              "the results of their actions, and provide a sense of atmosphere "
                              "through vivid and engaging descriptions."
                }
            ]

            for msg_content in reversed(channel_messages):
                messages.append({"role": "user", "content": msg_content})

            messages.append({"role": "user", "content": prompt})

            completion = await self.client.chat.completions.create(
                model='gpt-4',
                messages=messages,
                max_tokens=300,
                temperature=0.7,
            )

            response = completion.choices[0].message.content.strip()
            
            if include_roll_info:
                return (f"*{character.name}, your {stat} check result is {total} "
                       f"(rolled {roll} + modifier {character.get_stat_modifier(stat)}).* "
                       f"\n\n{response}")
            return response

        except Exception as e:
            logging.error(f"Error in GPT response: {e}")
            return "Sorry, I couldn't process that request."

class UIHelpers:
    """UI helper functions"""
    @staticmethod
    def create_progress_bar(current: int, maximum: int, length: int = 10) -> str:
        """Creates a visual progress bar"""
        try:
            if maximum <= 0:
                return "⬜" * length
            
            filled = int((current / maximum) * length)
            filled = max(0, min(filled, length))
            empty = length - filled
            
            bar = "⬛" * filled + "⬜" * empty
            percentage = int((current / maximum) * 100)
            
            return f"{bar} {percentage}%"
        except Exception as e:
            logging.error(f"Error creating progress bar: {e}")
            return "Error"
        
# Dictionary mapping channel IDs to Area instances
def get_area_by_channel(channel_id):
    return channel_areas.get(channel_id)

def get_area_inventory(channel_id):
    """Get or create the inventory for the area associated with a channel."""
    if channel_id not in channel_areas:
        channel_areas[channel_id] = []
    return channel_areas[channel_id]

def verify_guild_configs(bot):
    """
    Verify that all configured guilds are valid and accessible
    """
    for guild_id, config in GUILD_CONFIGS.items():
        # Check if this guild belongs to the current shard
        shard_id = (guild_id >> 22) % bot.shard_count if bot.shard_count else None
        if shard_id is not None and shard_id not in bot.shards:
            continue  # Skip if guild doesn't belong to this shard
            
        guild = bot.get_guild(guild_id)
        if not guild:
            logging.warning(f"Could not find guild {guild_id} (Shard: {shard_id})")
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

def assign_npcs_to_areas(area_lookup, npc_lookup):
    for area in area_lookup.values():
        area.npcs = [npc_lookup[npc_name] for npc_name in area.npc_names if npc_name in npc_lookup]

async def sync_commands(bot) -> bool:
    """Synchronize application commands with Discord.
    
    Args:
        bot: The bot instance to sync commands for
        
    Returns:
        bool: True if sync was successful, False otherwise
    """
    try:
        logging.info("Starting command synchronization...")
        
        # Get list of guild IDs from config
        guild_ids = list(GUILD_CONFIGS.keys())
        
        # Sync to each configured guild
        for guild_id in guild_ids:
            try:
                await bot.sync_guild_commands(guild_id)
                logging.info(f"Synced commands for guild {guild_id}")
            except Exception as e:
                logging.error(f"Failed to sync commands for guild {guild_id}: {e}")
                return False
        
        logging.info("Command synchronization complete")
        return True
        
    except Exception as e:
        logging.error(f"Error in command synchronization: {e}")
        return False

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
