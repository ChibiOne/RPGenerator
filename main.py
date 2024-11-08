# main.py
import discord
from discord.ext import commands
from utils.rate_limiter import RateLimit
import logging
from config.settings import REDIS_CONFIG
import utils
from cogs.bot_core import BotCore
from cogs.database import DatabaseManager
from cogs.state_manager import StateManager
from utils.character.session import SessionManager
from utils.character.equipment import EquipmentManager
from utils.items.manager import ItemManager


class RPGBot(discord.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rate_limiter = RateLimit()
        self.session_manager = SessionManager()
        self.item_manager = ItemManager()  # Create this if you haven't already
        self.equipment_manager = EquipmentManager(self.item_manager)

    async def process_application_commands(self, interaction: discord.Interaction):
        """Override to add rate limit handling"""
        if not interaction.application_command:
            return

        # Initialize item manager
        await self.item_manager.initialize()

        bucket = f"cmd:{interaction.application_command.name}:{interaction.guild_id}"
        wait_time = await self.rate_limiter.check_rate_limit(bucket)
        
        if wait_time > 0:
            try:
                await interaction.response.send_message(
                    f"This command is rate limited. Please try again in {wait_time:.1f} seconds.",
                    ephemeral=True
                )
                return
            except discord.errors.InteractionResponded:
                return
                
        try:
            await super().process_application_commands(interaction)
        except discord.HTTPException as e:
            if e.code == 429:  # Rate limit error
                reset_after = float(e.response.headers.get('X-RateLimit-Reset-After', 5))
                is_global = e.response.headers.get('X-RateLimit-Global', False)
                
                await self.rate_limiter.update_rate_limit(bucket, reset_after, is_global)
                
                try:
                    await interaction.response.send_message(
                        "This command is currently rate limited. Please try again later.",
                        ephemeral=True
                    )
                except discord.errors.InteractionResponded:
                    pass

# Initialize bot
bot = RPGBot()

# Load cogs
bot.load_extension('cogs.bot_core')

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot shutting down via keyboard interrupt...")
    except Exception as e:
        logging.error(f"Unexpected error during bot execution: {e}")
    finally:
        # Clean up any resources if needed
        logging.info("Bot shutdown complete")

@bot.event
async def on_ready():
    try:
        # Wait for all shards to be ready if sharding is enabled
        if bot.shard_count and not bot.is_closed():
            await bot.wait_until_ready()
            
        logging.info(f'Logged in as {bot.user.name}')
        logging.info(f'Shards: {bot.shard_count or 1}')
        logging.info(f'Current shard IDs: {list(bot.shards.keys()) if bot.shard_count else "No sharding"}')
        
        verify_character_data()
        verify_guild_configs(bot)
        await sync_commands(bot)
        
    except Exception as e:
        logging.error(f"Error in on_ready: {e}", exc_info=True)


# ---------------------------- #
#         Running the Bot      #
# ---------------------------- #


if __name__ == "__main__":
    if initialize_game_data():
        bot.run(DISCORD_BOT_TOKEN)
    else:
        logging.error("Failed to initialize game data. Bot startup aborted.")
else:
    logging.error("Failed to register commands. Bot startup aborted.")
