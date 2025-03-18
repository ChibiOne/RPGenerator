# utils/travel_system/ui.py
import discord
from discord.ui import View, Button
import time
from datetime import datetime
import random
from typing import List, Optional
from .core import TravelSystem
class TravelView(discord.ui.View):
    """UI View for handling travel progress and interactions"""
    
    def __init__(self, character, destination_area, travel_time, travel_mode=None, weather=None):
        super().__init__(timeout=None)  # No timeout since this needs to last for travel duration
        self.character = character
        self.destination = destination_area
        self.total_time = travel_time * (travel_mode["speed_multiplier"] if travel_mode else 1.0)
        self.start_time = time.time()
        self.last_update = self.start_time
        self.cancelled = False
        self.travel_mode = travel_mode or TravelMode.WALKING
        self.weather = weather
        self.encounters: List = []
        
        # Add cancel button
        self.add_item(CancelTravelButton())

    def get_embed(self):
        """Generate the travel status embed"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        progress = min(elapsed / self.total_time, 1.0)
        
        # Create the main embed
        embed = discord.Embed(
            title=f"{self.travel_mode['emoji']} Journey in Progress",
            color=discord.Color.blue()
        )

        # Show route
        route_display = (
            f"**From:** {self.character.current_area.name} (Danger Level {self.character.current_area.danger_level})\n"
            f"**To:** {self.destination.name} (Danger Level {self.destination.danger_level})\n"
            f"**Distance:** {TravelSystem.calculate_distance(self.character.current_area.coordinates, self.destination.coordinates):.1f} units\n"
            f"**Mode:** {self.travel_mode['name']}"
        )
        embed.add_field(name="Route", value=route_display, inline=False)

        # Create progress bar
        progress_length = 20
        filled = int(progress * progress_length)
        
        # Use different emojis based on character location in journey
        if filled == 0:
            progress_bar = f"{self.travel_mode['emoji']}" + "▱" * (progress_length - 1)
        elif filled >= progress_length:
            progress_bar = "▰" * (progress_length - 1) + "🏁"
        else:
            progress_bar = "▰" * (filled - 1) + f"{self.travel_mode['emoji']}" + "▱" * (progress_length - filled)

        # Calculate time remaining
        time_remaining = self.total_time - elapsed
        if time_remaining > 0:
            minutes = int(time_remaining // 60)
            seconds = int(time_remaining % 60)
            time_display = f"{minutes}m {seconds}s remaining"
        else:
            time_display = "Arriving..."

        embed.add_field(
            name="Progress",
            value=f"`{progress_bar}` ({time_display})",
            inline=False
        )

        # Add travel conditions
        conditions = self._get_travel_conditions()
        if conditions:
            embed.add_field(name="Conditions", value=conditions, inline=False)

        # Add any points of interest along the way
        points_of_interest = self._get_points_of_interest(progress)
        if points_of_interest:
            embed.add_field(name="Points of Interest", value=points_of_interest, inline=False)

        # Show any recent encounters
        if self.encounters:
            recent_encounters = "\n".join(
                f"• Level {enc.danger_level} - {enc.name}" 
                for enc in self.encounters[-3:]  # Show last 3 encounters
            )
            embed.add_field(name="Recent Events", value=recent_encounters, inline=False)

        # Show current status
        status = self._get_travel_status(progress)
        embed.add_field(name="Status", value=status, inline=False)

        return embed

    def _get_travel_conditions(self):
        """Get current travel conditions"""
        conditions = []
        
        # Time of day
        hour = datetime.now().hour
        if 6 <= hour < 12:
            conditions.append("🌅 Morning - The road is quiet and clear")
        elif 12 <= hour < 17:
            conditions.append("☀️ Afternoon - Good traveling weather")
        elif 17 <= hour < 20:
            conditions.append("🌅 Evening - Light is fading")
        else:
            conditions.append("🌙 Night - Traveling under starlight")

        # Add weather condition if present
        if self.weather:
            conditions.append(f"{self._get_weather_emoji()} {self.weather.name}: {self.weather.description}")

        # Add random conditions occasionally
        if random.random() < 0.3:
            conditions.append(random.choice([
                "💨 A gentle breeze aids your journey",
                "🌿 The path is well-maintained",
                "🍂 Fallen leaves crunch underfoot",
                "🌤️ Perfect weather for traveling",
                "🎶 Birds sing in the distance"
            ]))

        return "\n".join(conditions)

    def _get_weather_emoji(self):
        """Get emoji for current weather"""
        weather_emojis = {
            "Clear": "☀️",
            "Rain": "🌧️",
            "Storm": "⛈️",
            "Fog": "🌫️",
            "Strong Winds": "💨"
        }
        return weather_emojis.get(self.weather.name if self.weather else "Clear", "🌤️")

    def _get_points_of_interest(self, progress):
        """Generate points of interest based on progress"""
        if 0.2 < progress <= 0.4:
            return "🌳 You pass through a small grove of ancient trees"
        elif 0.4 < progress <= 0.6:
            return "💧 You come across a clear stream crossing your path"
        elif 0.6 < progress <= 0.8:
            return "🪨 You navigate around impressive rock formations"
        return None

    def _get_travel_status(self, progress):
        """Generate status message based on progress"""
        emoji = self.travel_mode['emoji']
        if progress < 0.25:
            return f"{emoji} You've just begun your journey, feeling fresh and ready for adventure."
        elif progress < 0.5:
            return f"{emoji} You've found your rhythm, making steady progress toward your destination."
        elif progress < 0.75:
            return f"{emoji} More than halfway there, you can almost make out your destination."
        elif progress < 1:
            return f"{emoji} The end of your journey is in sight!"
        else:
            return "🏁 You've arrived at your destination!"

class CancelTravelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Cancel Travel",
            emoji="✖️"
        )

    async def callback(self, interaction: discord.Interaction):
        view: TravelView = self.view
        if str(interaction.user.id) != view.character.user_id:
            await interaction.response.send_message(
                "You cannot cancel someone else's journey!",
                ephemeral=True
            )
            return

        view.cancelled = True
        for child in view.children:
            child.disabled = True  # Disable all buttons

        embed = view.get_embed()
        embed.title = "🛑 Journey Cancelled"
        embed.color = discord.Color.red()
        embed.set_field_at(
            -1,  # Update last field (status)
            name="Status",
            value="Journey cancelled. You have stopped at a safe point along the way.",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=view)

class TravelEmbed:
    """Helper class for generating travel-related embeds"""
    
    @staticmethod
    def weather_emojis() -> dict:
        """Get mapping of weather types to emojis"""
        return {
            "Clear": "☀️",
            "Rain": "🌧️",
            "Storm": "⛈️",
            "Fog": "🌫️",
            "Strong Winds": "💨"
        }

    @staticmethod
    def random_flavor_text() -> str:
        """Get random flavor text for travel conditions"""
        return random.choice([
            "💨 A gentle breeze aids your journey",
            "🌿 The path is well-maintained",
            "🍂 Fallen leaves crunch underfoot",
            "🌤️ Perfect weather for traveling",
            "🎶 Birds sing in the distance"
        ])

    @staticmethod
    def get_time_of_day_condition() -> str:
        """Get current time of day condition text"""
        hour = datetime.now().hour
        if 6 <= hour < 12:
            return "🌅 Morning - The road is quiet and clear"
        elif 12 <= hour < 17:
            return "☀️ Afternoon - Good traveling weather"
        elif 17 <= hour < 20:
            return "🌅 Evening - Light is fading"
        else:
            return "🌙 Night - Traveling under starlight"