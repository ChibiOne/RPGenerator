# cogs/travel_commands.py
import discord
from discord.ext import commands
import logging
import asyncio
from ..utils.travel_system import TravelSystem
from ..utils.redis_manager import ShardAwareRedisDB

class TravelCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.travel_system = TravelSystem(bot)

    async def destination_autocomplete(ctx: discord.AutocompleteContext):
        """Autocomplete function for travel destinations"""
        try:
            user_id = str(ctx.interaction.user.id)
            character = load_or_get_character(user_id)
            if not character or not character.current_area:
                return []
            connected_areas = character.current_area.connected_areas
            current = ctx.value.lower() if ctx.value else ""

            logging.info(f"Connected areas: {[f'{area.name} ({type(area)})' for area in connected_areas]}")
            
            def format_area_name(area):
                """Format area name with danger level and distance"""
                if not area.name:  # Validate area name exists
                    logging.warning(f"Area without name found in connected areas")
                    return None
                    
                # Start with the base name and validate
                if len(area.name) > 80:  # Leave room for additional info
                    logging.warning(f"Area name too long: {area.name}")
                    return area.name[:80]
                
                distance = calculate_distance(character.current_area.coordinates, area.coordinates)
                danger_emoji = "⚠️" if area.danger_level > character.current_area.danger_level else "✨" if area.danger_level < character.current_area.danger_level else "➡️"
                
                # Build the name in parts to ensure we don't exceed length
                name_parts = [
                    area.name,
                    f"[{danger_emoji} {area.danger_level}]",  # Simplified level display
                    f"({distance:.0f}u)"  # Shortened units display
                ]
                
                full_name = " ".join(name_parts)
                
                # Only add description if we have room (leaving margin for safety)
                if len(full_name) < 80 and area.description:
                    desc_space = 95 - len(full_name)  # Leave 5 chars margin
                    if desc_space > 10:  # Only add description if we have meaningful space
                        description_snippet = area.description[:desc_space].rstrip()
                        full_name += f" - {description_snippet}"
                
                # Final length check
                if len(full_name) > 100:
                    full_name = full_name[:97] + "..."
                elif len(full_name) < 1:
                    full_name = area.name  # Fallback to just the area name
                    
                return full_name

            choices = []
            for area in connected_areas:
                if not current or current in area.name.lower():
                    formatted_name = format_area_name(area)
                    if formatted_name:  # Only add if we got a valid formatted name
                        try:
                            choice = discord.OptionChoice(
                                name=formatted_name,
                                value=area.name
                            )
                            choices.append(choice)
                        except Exception as e:
                            logging.error(f"Failed to create option choice for area {area.name}: {e}")
                            continue
            
            # Log the choices being returned for debugging
            logging.info(f"Returning {len(choices)} choices")
            for choice in choices:
                logging.info(f"Choice name length: {len(choice.name)}, name: {choice.name}")
                
            return choices[:25]
        except Exception as e:
            logging.error(f"Error in travel autocomplete: {e}")
            return []

    @bot.slash_command(name="travel", description="Move to a connected area.")
    async def travel(
        ctx: discord.ApplicationContext,
        destination: str = discord.Option(
            description="The name of the area to move to.",
            autocomplete=destination_autocomplete
        )
    ):
        try:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild_id)
            
            # Load character using Redis
            character = await load_or_get_character_redis(bot, user_id, guild_id)
            
            if not character:
                await ctx.respond(
                    "You don't have a character yet. Use `/create_character` to get started.",
                    ephemeral=True
                )
                return

            # Find destination area (keeping existing logic)
            destination_area = None
            for area in character.current_area.connected_areas:
                if area.name.lower() == destination.lower():
                    destination_area = area
                    break

            if not destination_area:
                await ctx.respond(
                    f"You cannot travel to '{destination}' from here. Use /scene to see connected areas.",
                    ephemeral=True
                )
                return

            if character.is_traveling:
                await ctx.respond(
                    "You are already traveling. Wait until you arrive at your destination.",
                    ephemeral=True
                )
                return

            # Calculate travel time based on distance (keeping existing logic)
            travel_time = max(2, int(calculate_distance(
                character.current_area.coordinates,
                destination_area.coordinates
            )))

            # Set up character travel state
            character.is_traveling = True
            character.travel_destination = destination_area
            character.travel_end_time = time.time() + travel_time
            character.last_interaction_guild = ctx.guild_id

            # Save character state to Redis
            await bot.redis_player.set(
                f"character:{guild_id}:{user_id}",
                pickle.dumps(character.to_dict())
            )

            # Create travel view with mode and weather (keeping existing logic)
            travel_mode = TravelMode.WALKING
            if hasattr(character, 'mount') and character.mount:
                travel_mode = TravelMode.RIDING
                
            weather = random.choice(list(WEATHER_EFFECTS.values()))
            view = TravelView(character, destination_area, travel_time, travel_mode, weather)

            # Send initial travel message
            await ctx.respond(
                "Beginning your journey...",
                ephemeral=True
            )

            # Send travel view as DM
            try:
                await ctx.author.send(embed=view.get_embed(), view=view)
                logging.info(f"Travel details sent to user {user_id} via DM")
            except discord.Forbidden:
                await ctx.respond(
                    "I couldn't send you a DM. Please enable DMs from server members.",
                    ephemeral=True
                )
                return

            # Start travel task with Redis context
            asyncio.create_task(
                travel_task_redis(
                    bot=bot,
                    character=character,
                    user_id=user_id,
                    guild_id=guild_id,
                    destination_area=destination_area
                )
            )
            logging.info(f"User '{user_id}' started traveling to '{destination_area.name}'")

        except Exception as e:
            logging.error(f"Error in travel command: {e}", exc_info=True)
            await ctx.respond(
                "An error occurred while processing your travel request.",
                ephemeral=True
            )