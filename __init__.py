# project_root/__init__.py
from typing import Dict, List, Optional, Union, Any
from pathlib import Path

# Define project root path
PROJECT_ROOT = Path(__file__).parent

# Version info
__version__ = '0.1.0'

# Root level imports
from .config.settings import *
from .utils.redis_manager import RedisManager
from .utils.rate_limiter import RateLimiter
from .utils.game_loader import GameLoader
from .utils.shard_manager import ShardManager

# Utils directory __init__.py
from .items import ItemManager, Item
from .character import Character, CharacterSession
from .world import World, Area, Location

# Character module exports
__all__ = [
    'RedisManager',
    'RateLimiter',
    'GameLoader',
    'ShardManager',
    'ItemManager',
    'Item',
    'Character',
    'CharacterSession',
    'World',
    'Area',
    'Location'
]