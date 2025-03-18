import discord
import logging
from discord import ui
from discord.ui.input_text import InputTextStyle
from typing import Optional

from ..session import session_manager
from .embeds import create_character_progress_embed
from .character_creation_views import GenderSelectionView

class AbilityScoreModal(ui.Modal):
    """Modal for entering ability scores during character creation."""
    def __init__(self, user_id: str, ability_name: str, current_points: int):
        super().__init__(title=f"Set {ability_name} Score")
        self.user_id = user_id
        self.ability_name = ability_name
        self.current_points = current_points
        
        self.score = ui.InputText(
            label=f"{ability_name} Score",
            placeholder="Enter a value between 8 and 15...",
            min_length=1,
            max_length=2,
            style=InputTextStyle.short,
            required=True
        )
        self.add_item(self.score)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the modal submission.
        
        Args:
            interaction (discord.Interaction): The interaction that triggered this callback
        """
        try:
            session = session_manager.get_session(self.user_id)
            if not session:
                await interaction.response.send_message(
                    "Session expired. Please start character creation again.",
                    ephemeral=True
                )
                return

            # Validate input
            try:
                score = int(self.score.value)
                if not (8 <= score <= 15):
                    raise ValueError("Score must be between 8 and 15")
            except ValueError as e:
                await interaction.response.send_message(
                    f"Invalid score value: {e}",
                    ephemeral=True
                )
                return

            # Calculate points cost and verify
            points_cost = score - 8
            points_remaining = self.current_points - points_cost
            
            if points_remaining < 0:
                await interaction.response.send_message(
                    f"Not enough points remaining to set {self.ability_name} to {score}.",
                    ephemeral=True
                )
                return

            # Update session
            if 'stats' not in session.stats:
                session.stats = {}
            session.stats[self.ability_name] = score
            session.points_spent = self.current_points - points_remaining

            # Create embed
            embed = create_character_progress_embed(self.user_id, 6)
            
            from .views import AbilityScoresView
            await interaction.response.edit_message(
                content=f"{self.ability_name} set to {score}! Points remaining: {points_remaining}",
                embed=embed,
                view=AbilityScoresView(self.user_id, points_remaining)
            )
            
            logging.info(f"User {self.user_id} set {self.ability_name} to {score}")
            
        except Exception as e:
            logging.error(f"Error in AbilityScoreModal callback for user {self.user_id}: {e}")
            await interaction.response.send_message(
                "An error occurred while processing your ability score. Please try again.",
                ephemeral=True
            )

class CharacterNameModal(ui.Modal):
    """Modal for entering character name during character creation."""
    def __init__(self, user_id: str):
        """Initialize the modal.
        
        Args:
            user_id (str): Discord user ID
        """
        super().__init__(title="Enter Character Name")
        self.user_id = user_id
        self.character_name = ui.InputText(
            label="Character Name",
            placeholder="Enter your character's name...",
            min_length=2,
            max_length=32,
            style=InputTextStyle.short,
            required=True
        )
        self.add_item(self.character_name)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the modal submission.
        
        Args:
            interaction (discord.Interaction): The interaction that triggered this callback
        """
        try:
            session = session_manager.get_session(self.user_id)
            if not session:
                session = session_manager.create_session(self.user_id)

            session.name = self.character_name.value
            
            embed = create_character_progress_embed(self.user_id, 1)
            
            await interaction.response.send_message(
                content="Please select your gender:",
                embed=embed,
                view=GenderSelectionView(self.user_id),
                ephemeral=True
            )
            
            logging.info(f"User {self.user_id} entered name: {session.name}")
            
        except Exception as e:
            logging.error(f"Error in CharacterNameModal callback for user {self.user_id}: {e}")
            await interaction.response.send_message(
                "An error occurred while processing your character name. Please try again.",
                ephemeral=True
            )
