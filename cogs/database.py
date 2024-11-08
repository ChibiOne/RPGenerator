# cogs/database.py
import discord
from discord.ext import commands
import logging
from typing import Optional, List
from ..utils.redis_manager import ShardAwareRedisDB

class DatabaseManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.redis_manager = ShardAwareRedisDB(bot)

    async def cog_load(self):
        """Initialize database connections"""
        try:
            await self.redis_manager.init_pools()
            logging.info("Database Manager cog initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing Database Manager cog: {e}")
            raise

    async def get_character(self, user_id: str, guild_id: str) -> Optional['Character']:
        """Get character from Redis with guild context"""
        try:
            key = f"character:{guild_id}:{user_id}"
            data = await self.redis_manager.get(key, int(guild_id))
            if data:
                # Assuming Character class is imported
                return Character.from_dict(data, user_id, self.bot.get_area_lookup(guild_id))
            return None
        except Exception as e:
            logging.error(f"Error getting character for user {user_id} in guild {guild_id}: {e}")
            return None

    async def save_character(self, character: 'Character', guild_id: str) -> bool:
        """Save character to Redis with guild context"""
        try:
            key = f"character:{guild_id}:{character.user_id}"
            success = await self.redis_manager.set(key, character.to_dict(), int(guild_id))
            
            if success:
                # Update server's active characters list
                server_key = f"server:{guild_id}:characters"
                await self.redis_manager.sadd(server_key, character.user_id)
            return success
        except Exception as e:
            logging.error(f"Error saving character {character.user_id} in guild {guild_id}: {e}")
            return False

    async def get_area(self, area_name: str, guild_id: str) -> Optional['Area']:
        """Get area from Redis with server-specific override support"""
        try:
            # Check for server override first
            server_key = f"server:{guild_id}:area:{area_name}"
            data = await self.redis_manager.get(server_key, int(guild_id))
            
            if not data:
                # Fall back to global area
                global_key = f"area:{area_name}"
                data = await self.redis_manager.get(global_key)
                
            if data:
                return Area.from_dict(data)
            return None
        except Exception as e:
            logging.error(f"Error getting area {area_name} for guild {guild_id}: {e}")
            return None

    async def get_guild_config(self, guild_id: str) -> dict:
        """Get server-specific configuration"""
        try:
            key = f"server:{guild_id}:config"
            return await self.redis_manager.get(key, int(guild_id)) or {}
        except Exception as e:
            logging.error(f"Error getting config for guild {guild_id}: {e}")
            return {}

    async def get_active_characters(self, guild_id: str) -> List[str]:
        """Get list of active character IDs in a guild"""
        try:
            key = f"server:{guild_id}:characters"
            members = await self.redis_manager.smembers(key, int(guild_id))
            return list(members) if members else []
        except Exception as e:
            logging.error(f"Error getting active characters for guild {guild_id}: {e}")
            return []

def setup(bot):
    bot.add_cog(DatabaseManager(bot))