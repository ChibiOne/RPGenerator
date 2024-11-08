# config/settings.py
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# API Keys and Tokens
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DISCORD_APP_ID = os.getenv('DISCORD_APP_ID')

# Redis Configuration
REDIS_CONFIG = {
    'url': 'redis://localhost',
    'player_db': 0,
    'game_db': 1,
    'server_db': 2
}

# Guild Configurations
GUILD_CONFIGS = {
    1183315621690224640: {
        'channels': {'game': 1183315622558433342},
        'starting_area': "Marketplace Square",
        'command_prefix': '/',
    },
    817119234454192179: {
        'channels': {'game': 1012729890287652886},
        'starting_area': "Marketplace Square",
        'command_prefix': '/',
    },
}

# File Constants
FILE_PATHS = {
    'ACTIONS': 'actions.json',
    'CHARACTERS': 'characters.json',
    'ITEMS': 'items.json',
    'NPCS': 'npcs.json',
    'AREAS': 'areas.json',
    'LOCATIONS': 'locations.json',
    'REGIONS': 'regions.json',
    'CONTINENTS': 'continents.json',
    'WORLD': 'world.json',
}

# Game Constants
DEFAULT_STARTING_AREA = "Marketplace Square"
GLOBAL_COOLDOWN = 5
CACHE_DURATION = 300