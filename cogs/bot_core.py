# cogs/bot_core.py
import discord
from discord.ext import commands
import logging
from config.settings import REDIS_CONFIG
import redis.asyncio as redis

class BotCore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rate_limiter = RateLimit()
        self.redis_game = None
        self.redis_player = None
        self.redis_server = None
        self.synced_guilds = set()

    async def cog_load(self):
        """Initialize cog connections and data"""
        try:
            # Initialize Redis connections
            self.redis_game = await redis.from_url(
                REDIS_CONFIG['url'],
                db=REDIS_CONFIG['game_db'],
                decode_responses=False
            )
            self.redis_player = await redis.from_url(
                REDIS_CONFIG['url'],
                db=REDIS_CONFIG['player_db'],
                decode_responses=False
            )
            self.redis_server = await redis.from_url(
                REDIS_CONFIG['url'],
                db=REDIS_CONFIG['server_db'],
                decode_responses=False
            )
            
            # Load actions
            self.actions = await load_actions_redis(self.bot)
            
            logging.info("Bot Core cog initialized successfully")
        except Exception as e:
            logging.error(f"Error in bot core initialization: {e}")
            raise

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Handle new guild joins"""
        try:
            await self.bot.sync_guild_commands(guild.id)
        except Exception as e:
            logging.error(f"Error syncing commands for guild {guild.id}: {e}")

    @bot.slash_command(name="sync", description="Manually sync bot commands")
    @commands.has_permissions(administrator=True)
    async def sync(ctx: discord.ApplicationContext):
        """Manual command to sync commands to the current guild"""
        try:
            if ctx.guild_id not in GUILD_CONFIGS:
                await ctx.respond(
                    "This guild is not configured for command syncing.",
                    ephemeral=True
                )
                return

            synced = await bot.sync_commands()
            
            await ctx.respond(
                f"Successfully synced {len(synced)} commands to this guild!",
                ephemeral=True
            )
            logging.info(f"Manually synced commands to guild {ctx.guild_id}")
            
        except Exception as e:
            logging.error(f"Error in manual sync command: {e}")
            await ctx.respond(
                "Failed to sync commands.",
                ephemeral=True
            )

def setup(bot):
    bot.add_cog(BotCore(bot))