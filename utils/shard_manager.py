# utils/shard_manager.py
import discord
import logging
import asyncio
from typing import Dict, Any, Optional

async def setup_sharding(bot):
    """Set up sharding based on bot size and recommended shard count"""
    try:
        # Get recommended shard count from Discord
        data = await bot.http.get_bot_gateway()
        shard_count = data['shards']
        max_concurrency = data['session_start_limit']['max_concurrency']
        
        logging.info(f"Recommended shards: {shard_count}")
        logging.info(f"Max concurrency: {max_concurrency}")
        
        # Configure the bot for sharding
        bot.shard_count = shard_count
        
        # Initialize shards in buckets based on max_concurrency
        for i in range(0, shard_count, max_concurrency):
            shard_ids = list(range(i, min(i + max_concurrency, shard_count)))
            await bot.start_shards(shard_ids)
            
        logging.info(f"Successfully initialized {shard_count} shards")
        
    except Exception as e:
        logging.error(f"Error setting up sharding: {e}")
        raise

class ShardAwareStateManager:
    def __init__(self, bot):
        self.bot = bot
        self.shard_states: Dict[Optional[int], Dict[str, Any]] = {}
        self.lock = asyncio.Lock()

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

    async def get_value(self, guild_id: int, key: str, default: Any = None) -> Any:
        """Get a specific value from shard state"""
        state = await self.get_shard_state(guild_id)
        return state.get(key, default)

    async def increment_value(self, guild_id: int, key: str, amount: int = 1) -> int:
        """Increment a numeric value in shard state"""
        async with self.lock:
            state = await self.get_shard_state(guild_id)
            current = state.get(key, 0)
            new_value = current + amount
            state[key] = new_value
            return new_value

    async def cleanup_shard(self, shard_id: Optional[int]):
        """Clean up state for a specific shard"""
        async with self.lock:
            if shard_id in self.shard_states:
                del self.shard_states[shard_id]