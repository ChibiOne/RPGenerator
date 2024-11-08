# cogs/events/bot_events.py
import discord
from discord.ext import commands
import logging

class BotEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            if self.bot.shard_count and not self.bot.is_closed():
                await self.bot.wait_until_ready()
                
            logging.info(f'Logged in as {self.bot.user.name}')
            logging.info(f'Shards: {self.bot.shard_count or 1}')
            logging.info(f'Current shard IDs: {list(self.bot.shards.keys()) if self.bot.shard_count else "No sharding"}')
            
            verify_character_data()
            verify_guild_configs(self.bot)
            await sync_commands(self.bot)
            
        except Exception as e:
            logging.error(f"Error in on_ready: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        shard_id = (guild.id >> 22) % self.bot.shard_count if self.bot.shard_count else None
        if shard_id is not None and shard_id not in self.bot.shards:
            return

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        shard_id = (guild.id >> 22) % self.bot.shard_count if self.bot.shard_count else None
        if shard_id is not None and shard_id not in self.bot.shards:
            return

    @commands.Cog.listener()
    async def on_shutdown(self):
        save_characters(characters)
        logging.info("Bot is shutting down. Character data saved.")

def setup(bot):
    bot.add_cog(BotEvents(bot))