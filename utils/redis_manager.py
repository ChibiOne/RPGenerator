# utils/redis_manager.py

import redis.asyncio as redis
import pickle
import logging
import asyncio
from typing import Optional, Dict, Any, List
from config.settings import REDIS_CONFIG, CHARACTERS_FILE

class ShardAwareRedisDB:
    def __init__(self, bot):
        self.bot = bot
        self.redis_pools: Dict[int, redis.Redis] = {}
        self.default_ttl = 3600
        self.lock = asyncio.Lock()

    async def init_pools(self):
        """Initialize Redis connection pools for each shard"""
        try:
            for shard_id in (self.bot.shards.keys() if self.bot.shard_count else [None]):
                pool = await redis.from_url(
                    REDIS_CONFIG['url'],
                    encoding='utf-8',
                    decode_responses=False,
                    max_connections=10
                )
                self.redis_pools[shard_id] = pool
                
            logging.info(f"Initialized Redis pools for {len(self.redis_pools)} shards")
        except Exception as e:
            logging.error(f"Failed to initialize Redis pools: {e}")
            raise

    def get_key(self, guild_id: Optional[int], key: str) -> str:
        """Generate Redis key with shard-specific prefix"""
        shard_id = (guild_id >> 22) % self.bot.shard_count if guild_id and self.bot.shard_count else 'global'
        return f"shard:{shard_id}:{key}"

    async def get_pool(self, guild_id: Optional[int] = None) -> redis.Redis:
        """Get Redis pool for the appropriate shard"""
        shard_id = (guild_id >> 22) % self.bot.shard_count if guild_id and self.bot.shard_count else None
        if shard_id not in self.redis_pools:
            await self.init_pools()
        return self.redis_pools.get(shard_id, self.redis_pools[None])

    # Basic Redis Operations
    async def set(self, key: str, value: Any, guild_id: Optional[int] = None, 
                  expire: Optional[int] = None) -> bool:
        try:
            redis = await self.get_pool(guild_id)
            full_key = self.get_key(guild_id, key)
            
            # Serialize complex objects
            if isinstance(value, (dict, list, 'Character', 'Area')):
                value = pickle.dumps(value)
            
            if expire is None:
                expire = self.default_ttl
                
            await redis.set(full_key, value, ex=expire)
            return True
        except Exception as e:
            logging.error(f"Redis set error for key {key}: {e}")
            return False

    async def get(self, key: str, guild_id: Optional[int] = None) -> Any:
        try:
            redis = await self.get_pool(guild_id)
            full_key = self.get_key(guild_id, key)
            value = await redis.get(full_key)
            
            if value is None:
                return None
                
            try:
                return pickle.loads(value)
            except:
                return value
        except Exception as e:
            logging.error(f"Redis get error for key {key}: {e}")
            return None

    async def delete(self, key: str, guild_id: Optional[int] = None) -> bool:
        try:
            redis = await self.get_pool(guild_id)
            full_key = self.get_key(guild_id, key)
            await redis.delete(full_key)
            return True
        except Exception as e:
            logging.error(f"Redis delete error for key {key}: {e}")
            return False

    # Character Operations
    async def save_character(self, character: 'Character') -> bool:
        try:
            guild_id = character.last_interaction_guild
            key = f"character:{character.user_id}"
            return await self.set(key, character, guild_id)
        except Exception as e:
            logging.error(f"Error saving character {character.user_id}: {e}")
            return False

    async def load_character(self, user_id: str, guild_id: Optional[int] = None) -> Optional['Character']:
        try:
            key = f"character:{user_id}"
            return await self.get(key, guild_id)
        except Exception as e:
            logging.error(f"Error loading character {user_id}: {e}")
            return None

    # Area Operations
    async def save_area(self, area: 'Area') -> bool:
        try:
            key = f"area:{area.name}"
            return await self.set(key, area)
        except Exception as e:
            logging.error(f"Error saving area {area.name}: {e}")
            return False

    async def load_area(self, area_name: str) -> Optional['Area']:
        try:
            key = f"area:{area_name}"
            return await self.get(key)
        except Exception as e:
            logging.error(f"Error loading area {area_name}: {e}")
            return None

    # Batch Operations
    async def save_all_characters(self, characters: Dict[str, 'Character']) -> bool:
        try:
            async with self.lock:
                tasks = [
                    self.save_character(character)
                    for character in characters.values()
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return all(not isinstance(r, Exception) for r in results)
        except Exception as e:
            logging.error(f"Error in batch character save: {e}")
            return False

    # Migration Helpers
    async def migrate_from_json(self, characters_file: str = CHARACTERS_FILE):
        try:
            characters = await load_all_shards(self.bot)
            if characters:
                await self.save_all_characters(characters)
                logging.info(f"Successfully migrated {len(characters)} characters to Redis")
        except Exception as e:
            logging.error(f"Error migrating data to Redis: {e}")
    
    async def sadd(self, key: str, value: Any, guild_id: Optional[int] = None) -> bool:
        """Add value to a Redis set"""
        try:
            redis = await self.get_pool(guild_id)
            full_key = self.get_key(guild_id, key)
            await redis.sadd(full_key, value)
            return True
        except Exception as e:
            logging.error(f"Redis sadd error for key {key}: {e}")
            return False

    async def smembers(self, key: str, guild_id: Optional[int] = None) -> set:
        """Get all members of a Redis set"""
        try:
            redis = await self.get_pool(guild_id)
            full_key = self.get_key(guild_id, key)
            return await redis.smembers(full_key)
        except Exception as e:
            logging.error(f"Redis smembers error for key {key}: {e}")
            return set()