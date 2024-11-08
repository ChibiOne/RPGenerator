# utils/travel_system.py
import discord
import logging
import asyncio
import random
import math
from typing import Optional, Tuple, Dict
from .redis_manager import ShardAwareRedisDB
from .encounter_manager import EncounterManager
from typing import Optional, Tuple, Dict, List
import time
import pickle

class TravelSystem:
    def __init__(self, bot):
        self.bot = bot
        self.redis_db = ShardAwareRedisDB(bot)
        self.area_cache = {}
        self.encounter_manager = EncounterManager(self.redis_db)
        self.logger = logging.getLogger('travel_system')

    def calculate_distance(self, coord1: Tuple[float, float], 
                         coord2: Tuple[float, float]) -> float:
        """Calculate distance between two coordinates."""
        return math.hypot(coord2[0] - coord1[0], coord2[1] - coord1[1])

    def get_travel_time(self, character: 'Character', 
                       destination: 'Area') -> float:
        """Calculate travel time accounting for character's speed and distance"""
        base_time = max(2, int(self.calculate_distance(
            character.current_area.coordinates,
            destination.coordinates
        )))
        
        speed_modifier = character.movement_speed / 30.0
        return base_time / speed_modifier

    def create_scene_embed(self, area: 'Area') -> discord.Embed:
        """Creates an embed for scene description"""
        try:
            embed = discord.Embed(
                title=area.name,
                description=area.description,
                color=discord.Color.green()
            )

            # Connected Areas
            if hasattr(area, 'connected_areas') and area.connected_areas:
                connected_area_names = ', '.join(f"**{connected_area.name}**" 
                                            for connected_area in area.connected_areas)
                embed.add_field(
                    name="Connected Areas",
                    value=connected_area_names,
                    inline=False
                )
            else:
                embed.add_field(name="Connected Areas", value="None", inline=False)

            # NPCs
            if hasattr(area, 'npcs') and area.npcs:
                npc_names = ', '.join(f"**{npc.name}**" for npc in area.npcs)
                embed.add_field(name="NPCs Present", value=npc_names, inline=False)
            else:
                embed.add_field(name="NPCs Present", value="None", inline=False)

            # Items
            if hasattr(area, 'inventory') and area.inventory:
                item_names = ', '.join(f"**{item.name}**" 
                                    for item in area.inventory if hasattr(item, 'name'))
                embed.add_field(
                    name="Items Available",
                    value=item_names if item_names else "None",
                    inline=False
                )
            else:
                embed.add_field(name="Items Available", value="None", inline=False)

            return embed
        except Exception as e:
            self.logger.error(f"Error creating scene embed: {e}", exc_info=True)
            return None

    async def process_travel(self, character: 'Character', user_id: str, 
                           guild_id: str, view: 'TravelView'):
        """Process the travel task with Redis and party support"""
        try:
            # Check cross-shard travel
            if character.travel_destination:
                current_shard = (int(guild_id) >> 22) % self.bot.shard_count
                dest_guild_id = character.travel_destination.channel_id
                dest_shard = (dest_guild_id >> 22) % self.bot.shard_count
                
                if current_shard != dest_shard:
                    self.logger.info(f"Cross-shard travel: {current_shard} -> {dest_shard}")

            # Handle party
            party = await self.get_party(guild_id, user_id)
            travel_time = self.get_travel_time(character, character.travel_destination)
            
            if party:
                travel_time = await self.adjust_party_travel_time(party, travel_time)

            # Process travel
            await self.handle_travel_progress(character, user_id, guild_id, view, 
                                           travel_time, party)

        except Exception as e:
            self.logger.error(f"Error in travel process: {e}")

    async def get_area(self, area_name: str, guild_id: Optional[str] = None) -> Optional[Area]:
        """
        Fetches an area, checking server-specific overrides first if guild_id is provided
        """
        cache_key = f"{guild_id}:{area_name}" if guild_id else area_name
        
        # Check cache first
        if cache_key in self.area_cache:
            return self.area_cache[cache_key]

        try:
            # Check for server-specific override if guild_id provided
            if guild_id:
                server_area = await self.bot.redis_server.get(f"server:{guild_id}:area:{area_name}")
                if server_area:
                    area_data = pickle.loads(server_area)
                    area = Area(
                        name=area_data['name'],
                        description=area_data.get('description', ''),
                        coordinates=tuple(area_data.get('coordinates', (0, 0))),
                        connected_area_names=area_data.get('connected_area_names', []),
                        channel_id=area_data.get('channel_id'),
                        allows_intercontinental_travel=area_data.get('allows_intercontinental_travel', False),
                        danger_level=area_data.get('danger_level', 0)
                    )
                    self.area_cache[cache_key] = area
                    return area

            # Fetch from global areas
            area_data = await self.bot.redis_game.hget("areas", area_name)
            if not area_data:
                return None
            
            area_dict = pickle.loads(area_data)
            area = Area(
                name=area_dict['name'],
                description=area_dict.get('description', ''),
                coordinates=tuple(area_dict.get('coordinates', (0, 0))),
                connected_area_names=area_dict.get('connected_area_names', []),
                channel_id=area_dict.get('channel_id'),
                allows_intercontinental_travel=area_dict.get('allows_intercontinental_travel', False),
                danger_level=area_dict.get('danger_level', 0)
            )
            
            self.area_cache[cache_key] = area
            return area

        except Exception as e:
            self.logger.error(f"Error fetching area {area_name}: {str(e)}")
            return None

    async def can_travel(self, 
                        character: Character,
                        destination_area: Area,
                        guild_id: str) -> Tuple[bool, str]:
        """
        Checks if travel between areas is possible
        Returns: (can_travel: bool, reason: str)
        """
        try:
            if not destination_area:
                return False, "Destination area does not exist"

            if character.is_traveling:
                return False, "You are already traveling"

            # Check if areas are connected
            if destination_area.name not in [area.name for area in character.current_area.connected_areas]:
                return False, f"You cannot travel to {destination_area.name} from here"

            # Check for intercontinental travel
            if (character.current_area.allows_intercontinental_travel != 
                destination_area.allows_intercontinental_travel):
                if not character.current_area.allows_intercontinental_travel:
                    return False, "You must be at a port to travel to this destination"

            return True, "Travel possible"

        except Exception as e:
            self.logger.error(f"Error checking travel possibility: {str(e)}")
            return False, "An error occurred while checking travel possibility"

    async def start_travel(self,
                          character: Character,
                          destination_area: Area,
                          guild_id: str,
                          user_id: str) -> Tuple[bool, str, Optional[TravelView]]:
        """
        Initiates travel for a character
        Returns: (success: bool, message: str, travel_view: Optional[TravelView])
        """
        try:
            # Check if travel is possible
            can_travel, reason = await self.can_travel(character, destination_area, guild_id)
            if not can_travel:
                return False, reason, None

            # Calculate travel time
            travel_time = max(2, int(calculate_distance(
                character.current_area.coordinates,
                destination_area.coordinates
            )))

            # Set up travel state
            character.is_traveling = True
            character.travel_destination = destination_area
            character.travel_end_time = time.time() + travel_time
            character.last_interaction_guild = int(guild_id)

            # Save character state to Redis
            await self.bot.redis_player.set(
                f"character:{guild_id}:{user_id}",
                pickle.dumps(character.to_dict())
            )

            # Set up travel view with mount check
            travel_mode = TravelMode.RIDING if hasattr(character, 'mount') and character.mount else TravelMode.WALKING
            weather = random.choice(list(WEATHER_EFFECTS.values()))
            view = TravelView(character, destination_area, travel_time, travel_mode, weather)

            return True, "Travel initiated successfully", view

        except Exception as e:
            self.logger.error(f"Error starting travel: {str(e)}")
            return False, "An error occurred while starting travel", None

    async def complete_travel(self,
                            character: Character,
                            user_id: str,
                            guild_id: str,
                            view: TravelView) -> Tuple[bool, str]:
        """
        Completes the travel process and updates character location
        """
        try:
            if not view.cancelled:
                # Move character to new area
                success = character.move_to_area(character.travel_destination)
                if not success:
                    return False, "Failed to move to destination area"

                # Update character state
                character.is_traveling = False
                character.travel_destination = None
                character.travel_end_time = None

                # Save to Redis
                await self.bot.redis_player.set(
                    f"character:{guild_id}:{user_id}",
                    pickle.dumps(character.to_dict())
                )

                return True, "Travel completed successfully"
            
            return False, "Travel was cancelled"

        except Exception as e:
            self.logger.error(f"Error completing travel: {str(e)}")
            return False, "An error occurred while completing travel"

    async def cancel_travel(self,
                          character: Character,
                          user_id: str,
                          guild_id: str) -> bool:
        """
        Cancels ongoing travel and updates character state
        """
        try:
            character.is_traveling = False
            character.travel_destination = None
            character.travel_end_time = None

            await self.bot.redis_player.set(
                f"character:{guild_id}:{user_id}",
                pickle.dumps(character.to_dict())
            )
            
            return True
        except Exception as e:
            self.logger.error(f"Error cancelling travel: {str(e)}")
            return False
    async def get_party(self, guild_id: str, user_id: str) -> Optional['TravelParty']:
        """Get party information from Redis"""
        try:
            party_key = f"party:{guild_id}:{user_id}"
            party_data = await self.redis_db.get(party_key)
            if party_data:
                return await TravelParty.from_dict(pickle.loads(party_data), self.bot)
            return None
        except Exception as e:
            self.logger.error(f"Error getting party: {e}")
            return None

    async def adjust_party_travel_time(self, party: 'TravelParty', base_time: float) -> float:
        """Adjust travel time based on party composition"""
        try:
            slowest_member = party.get_slowest_member()
            return max(base_time, self.get_travel_time(slowest_member, party.leader.travel_destination))
        except Exception as e:
            self.logger.error(f"Error adjusting party travel time: {e}")
            return base_time

    async def handle_travel_progress(self, character: 'Character', user_id: str, 
                                guild_id: str, view: 'TravelView', 
                                travel_time: float, party: Optional['TravelParty']):
        """Handle the travel progress updates and completion"""
        try:
            message = await self.bot.get_user(int(user_id)).send(
                embed=view.get_embed(),
                view=view
            )

            update_interval = 5  # Update every 5 seconds
            next_update = time.time() + update_interval

            while time.time() < character.travel_end_time and not view.cancelled:
                if time.time() >= next_update:
                    try:
                        await message.edit(embed=view.get_embed())
                    except discord.NotFound:
                        break
                        
                    next_update = time.time() + update_interval
                    
                await asyncio.sleep(1)

            if not view.cancelled:
                # Complete the journey
                success, msg = await self.complete_travel(character, user_id, guild_id, view)

                if success and party:
                    # Move all party members
                    for member_id, member in party.members.items():
                        if member_id != user_id:
                            await self.complete_travel(member, member_id, guild_id, view)

                # Update final message
                final_embed = view.get_embed()
                final_embed.title = "🏁 Journey Complete!"
                final_embed.color = discord.Color.green()
                
                for child in view.children:
                    child.disabled = True
                    
                await message.edit(embed=final_embed, view=view)

                # Send arrival info
                scene_embed = self.create_scene_embed(character.current_area)
                await self.send_arrival_notifications(character, user_id, guild_id, scene_embed, party)

        except Exception as e:
            self.logger.error(f"Error handling travel progress: {e}")

    async def send_arrival_notifications(self, character: 'Character', user_id: str, 
                                    guild_id: str, scene_embed: discord.Embed, 
                                    party: Optional['TravelParty']):
        """Send arrival notifications to the user and guild"""
        try:
            # Send to user
            await self.bot.get_user(int(user_id)).send(
                f"You have arrived at **{character.current_area.name}**!",
                embed=scene_embed
            )

            # Send to guild channel
            guild_config = await self.bot.get_guild_config(guild_id)
            if guild_config:
                channel_id = guild_config.get('channels', {}).get('game')
                if channel_id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        if party:
                            member_names = ", ".join(c.name for c in party.members.values())
                            await channel.send(
                                f"The party ({member_names}) has arrived in **{character.current_area.name}**",
                                embed=scene_embed
                            )
                        else:
                            await channel.send(
                                f"**{character.name}** has arrived in **{character.current_area.name}**",
                                embed=scene_embed
                            )
        except Exception as e:
            self.logger.error(f"Error sending arrival notifications: {e}")
            
# Create separate files for these classes
class TravelMode:
    # [Previous TravelMode implementation]
    pass

class WeatherEffect:
    WALKING = {"name": "Walking", "speed_multiplier": 1.0, "emoji": "🚶"}
    RIDING = {"name": "Horseback", "speed_multiplier": 2.0, "emoji": "🐎"}
    CARRIAGE = {"name": "Carriage", "speed_multiplier": 1.5, "emoji": "🛒"}
    RUNNING = {"name": "Running", "speed_multiplier": 1.3, "emoji": "🏃"}

    def __init__(self, name, description, speed_modifier, danger_level):
            self.name = name
            self.description = description
            self.speed_modifier = speed_modifier  # Multiplier for travel time
            self.danger_level = danger_level  # Affects encounter chance

    WEATHER_EFFECTS = {
    "clear": WeatherEffect(
        "Clear", 
        "Perfect traveling weather", 
        1.0,  # Normal speed
        1.0   # Normal danger
    ),
    "rain": WeatherEffect(
        "Rain", 
        "The rain makes travel slower", 
        1.3,  # 30% slower
        1.2   # 20% more dangerous
    ),
    "storm": WeatherEffect(
        "Storm", 
        "Thunder and lightning make travel dangerous", 
        1.8,  # 80% slower
        1.5   # 50% more dangerous
    ),
    "fog": WeatherEffect(
        "Fog", 
        "Limited visibility slows your progress", 
        1.4,  # 40% slower
        1.3   # 30% more dangerous
    ),
    "wind": WeatherEffect(
        "Strong Winds", 
        "The wind howls around you", 
        1.2,  # 20% slower
        1.1   # 10% more dangerous
    )
}