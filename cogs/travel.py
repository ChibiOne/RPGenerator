import discord
from discord.ext import commands
import logging
from utils.travel_system import TravelSystem as TravelManager

class TravelSystem(commands.Cog):
    """Travel system cog for handling character movement between areas"""
    
    def __init__(self, bot):
        self.bot = bot
        self.travel_manager = TravelManager(bot)
        self.logger = logging.getLogger('cogs.travel')

    @commands.slash_command(
        name="travel",
        description="Travel to a different area"
    )
    async def travel_command(
        self,
        ctx: discord.ApplicationContext,
        destination: str
    ):
        """
        Travel to a specified destination
        
        Parameters
        ----------
        destination : str
            The name of the destination area
        """
        try:
            # Defer response since travel might take time
            await ctx.defer()

            # Get character data
            character = await self.bot.get_character(str(ctx.author.id), str(ctx.guild.id))
            if not character:
                await ctx.respond("You don't have a character! Use /create_character to make one.")
                return

            # Get destination area
            destination_area = await self.travel_manager.get_area(destination, str(ctx.guild.id))
            if not destination_area:
                await ctx.respond(f"Could not find area: {destination}")
                return

            # Attempt to start travel
            success, message, view = await self.travel_manager.start_travel(
                character,
                destination_area,
                str(ctx.guild.id),
                str(ctx.author.id)
            )

            if not success:
                await ctx.respond(message)
                return

            # Initiate travel process
            await ctx.respond(f"Beginning travel to {destination_area.name}...")
            
            await self.travel_manager.process_travel(
                character,
                str(ctx.author.id),
                str(ctx.guild.id),
                view
            )

        except Exception as e:
            self.logger.error(f"Error in travel command: {e}", exc_info=True)
            await ctx.respond("An error occurred while processing your travel request.")

    @commands.slash_command(
        name="cancel_travel",
        description="Cancel ongoing travel"
    )
    async def cancel_travel_command(self, ctx: discord.ApplicationContext):
        """Cancel ongoing travel if any is in progress"""
        try:
            character = await self.bot.get_character(str(ctx.author.id), str(ctx.guild.id))
            if not character:
                await ctx.respond("You don't have a character!")
                return

            if not character.is_traveling:
                await ctx.respond("You are not currently traveling!")
                return

            success = await self.travel_manager.cancel_travel(
                character,
                str(ctx.author.id),
                str(ctx.guild.id)
            )

            if success:
                await ctx.respond("Travel cancelled successfully.")
            else:
                await ctx.respond("Failed to cancel travel.")

        except Exception as e:
            self.logger.error(f"Error in cancel travel command: {e}", exc_info=True)
            await ctx.respond("An error occurred while cancelling travel.")