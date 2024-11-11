# cogs/events/error_handler.py
import discord
from discord.ext import commands
import logging

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_application_command_error(self, ctx: discord.ApplicationContext, 
                                         error: discord.DiscordException):
        try:
            if isinstance(error, discord.errors.CheckFailure):
                await ctx.respond("You don't have permission to use this command.", 
                                ephemeral=True)
            elif isinstance(error, discord.HTTPException) and error.code == 429:
                retry_after = error.retry_after
                await ctx.respond(
                    f"This command is rate limited. Please try again in {retry_after:.1f} seconds.",
                    ephemeral=True
                )
            else:
                shard_id = self.bot.get_shard(ctx.guild_id) if ctx.guild else None
                logging.error(f"Command error in guild {ctx.guild_id} (Shard {shard_id}): {error}")
                await ctx.respond("An error occurred while processing your command.", 
                                ephemeral=True)
        except Exception as e:
            logging.error(f"Error in error handler: {e}")

def setup(bot):
    bot.add_cog(ErrorHandler(bot))