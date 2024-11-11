# cogs/state_manager.py
import discord
from discord.ext import commands
import logging
import asyncio
from typing import Dict, Any

class StateManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.shard_states = {}
        self.lock = asyncio.Lock()

    async def cog_load(self):
        """Initialize state management"""
        try:
            logging.info("State Manager cog initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing State Manager cog: {e}")
            raise

    async def get_shard_state(self, guild_id: int) -> Dict[str, Any]:
        """Get state for the shard that handles this guild"""
        shard_id = (guild_id >> 22) % self.bot.shard_count if self.bot.shard_count else None
        async with self.lock:
            if shard_id not in self.shard_states:
                self.shard_states[shard_id] = {}
            return self.shard_states[shard_id]

    async def update_shard_state(self, guild_id: int, key: str, value: Any):
        """Update state for a specific shard"""
        state = await self.get_shard_state(guild_id)
        async with self.lock:
            state[key] = value

    async def clear_shard_state(self, guild_id: int):
        """Clear state for a specific shard"""
        shard_id = (guild_id >> 22) % self.bot.shard_count if self.bot.shard_count else None
        async with self.lock:
            self.shard_states[shard_id] = {}

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Initialize state for new guild"""
        await self.clear_shard_state(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Clean up state when removed from guild"""
        await self.clear_shard_state(guild.id)

def setup(bot):
    bot.add_cog(StateManager(bot))