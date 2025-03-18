# utils/game_loader.py

import logging
from typing import Dict, Optional, Any

# Local imports
from .redis_manager import ShardAwareRedisDB

# Game object imports
from .game_objects.items import Item
from .game_objects.character import Character
from .game_objects.npc import NPC
from .game_objects.world.area import Area
from .game_objects.world.location import Location
from .game_objects.world.region import Region
from .game_objects.world.continent import Continent
from .game_objects.world.world import World

async def load_actions_redis(redis_db: ShardAwareRedisDB) -> Dict[str, Any]:
    """
    Loads actions from Redis.
    Args:
        redis_db: Redis database manager
    Returns:
        dict: A dictionary mapping actions to their associated stats.
    """
    try:
        actions = await redis_db.get("actions")
        if actions:
            logging.info("Actions loaded successfully from Redis.")
            return actions
        else:
            logging.warning("No actions found in Redis.")
            return {}
           
    except Exception as e:
        logging.error(f"Error loading actions from Redis: {e}")
        return {}

async def load_game_data(bot) -> Dict[str, Any]:
    """
    Load all game data from Redis and return reference dictionary.
    Args:
        bot: The bot instance for Redis connection
    Returns:
        dict: Dictionary containing all game data references
    """
    try:
        logging.info("Starting to load game data...")
        redis_db = ShardAwareRedisDB(bot)
        
        # Initialize data stores
        game_data = {}
        
        # Load actions
        action_lookup = await load_actions_redis(redis_db)
        if not action_lookup:
            logging.error("Failed to load actions")
            return {}
        game_data['actions'] = action_lookup
        logging.info(f"Loaded {len(action_lookup)} actions")

        # Load items
        item_lookup = await redis_db.get('items') or {}
        game_data['items'] = item_lookup
        logging.info(f"Loaded {len(item_lookup)} items")

        # Load areas
        area_lookup = await redis_db.get('areas') or {}
        game_data['areas'] = area_lookup
        logging.info(f"Loaded {len(area_lookup)} areas")

        # Load NPCs
        npc_lookup = await redis_db.get('npcs') or {}
        game_data['npcs'] = npc_lookup
        logging.info(f"Loaded {len(npc_lookup)} NPCs")

        # Resolve area connections and NPCs
        if not await resolve_area_connections_and_npcs(redis_db, area_lookup, npc_lookup):
            logging.error("Failed to resolve area connections and NPCs")
            return {}

        # Store complete game data in Redis
        await redis_db.set('game_data', game_data)
        
        logging.info(f"Game data loaded with keys: {game_data.keys()}")
        logging.info(f"Area lookup contains {len(area_lookup)} areas: {list(area_lookup.keys())}")
        
        return game_data

    except Exception as e:
        logging.error(f"Error in load_game_data: {e}")
        return {}

def initialize_game_data() -> bool:
    """
    Initialize game data and verify loaded correctly.
    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        from pathlib import Path
        data_dir = Path('data')
        
        # Verify required data files exist
        required_files = ['actions.json', 'items.json', 'npcs.json', 'areas.json']
        for file in required_files:
            if not (data_dir / file).exists():
                logging.error(f"Required data file {file} not found")
                return False
        
        logging.info("Data files verified successfully")
        return True
        
    except Exception as e:
        logging.error(f"Error initializing game data: {e}")
        return False

async def resolve_area_connections_and_npcs(redis_db: ShardAwareRedisDB, 
                                          area_lookup: Dict[str, Any], 
                                          npc_lookup: Dict[str, Any]) -> bool:
    """
    Resolves and caches area connections and NPCs in Redis.
    Args:
        redis_db: Redis database manager
        area_lookup: Dictionary mapping area names to Area instances
        npc_lookup: Dictionary mapping NPC names to NPC instances
    """
    try:
        # Check if we have cached connections
        cached_connections = await redis_db.get('area_connections_cache')
        if cached_connections:
            logging.info("Using cached area connections")
            for area_name, connections in cached_connections.items():
                if area := area_lookup.get(area_name):
                    area.connected_areas = [area_lookup.get(name) for name in connections['areas']]
                    area.npcs = [npc_lookup.get(name) for name in connections['npcs']]
            return True

        # If no cache, resolve connections
        logging.info("Starting area and NPC resolution")
        logging.info(f"Available areas: {list(area_lookup.keys())}")
        logging.info(f"Available NPCs: {list(npc_lookup.keys())}")

        # Store connections for caching
        connections_cache = {}

        for area in area_lookup.values():
            logging.info(f"\nProcessing area: {area.name}")
            logging.info(f"Looking for connected areas: {area.connected_area_names}")
            logging.info(f"Looking for NPCs: {area.npc_names}")

            # Initialize cache entry for this area
            connections_cache[area.name] = {
                'areas': [],
                'npcs': []
            }

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
                    connections_cache[area.name]['areas'].append(connected_area.name)
                    logging.info(f"Successfully connected area '{area.name}' to '{name}'")
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
                    connections_cache[area.name]['npcs'].append(npc.name)
                    logging.info(f"Successfully added NPC '{npc_name}' to area '{area.name}'")
                else:
                    logging.warning(f"NPC '{npc_name}' not found for area '{area.name}'")
                    logging.info(f"Available NPCs were: {list(npc_lookup.keys())}")
            
            area.npcs = resolved_npcs

            # Store updated area in Redis
            await redis_db.set(f"area:{area.name}", area)

        # Cache the connections
        await redis_db.set('area_connections_cache', connections_cache, expire=86400)  # Cache for 24 hours
        
        logging.info("Completed area and NPC resolution")
        return True

    except Exception as e:
        logging.error(f"Error in resolve_area_connections_and_npcs: {e}", exc_info=True)
        return False

async def invalidate_area_connections_cache(redis_db: ShardAwareRedisDB):
    """
    Invalidate the area connections cache when areas or NPCs are modified.
    """
    try:
        await redis_db.delete('area_connections_cache')
        logging.info("Area connections cache invalidated")
        return True
    except Exception as e:
        logging.error(f"Error invalidating area connections cache: {e}")
        return False

# Get area helper function
def get_area_by_name(area_name: str, area_lookup: Dict[str, Area]) -> Area:
    """
    Retrieve an area by name from the lookup dictionary.
    Args:
        area_name: Name of the area to retrieve
        area_lookup: Dictionary of areas
    Returns:
        Area: The requested area
    Raises:
        ValueError: If area doesn't exist
    """
    area = area_lookup.get(area_name)
    if not area:
        raise ValueError(f"Area '{area_name}' does not exist.")
    return area