"""UI views for handling ability scores."""
import logging
import discord
from discord import ui
from typing import Dict, Any

from ..session import session_manager
from .core_components import AbilitySelect
from .modals import AbilityScoreModal

class AbilityScoresView(ui.View):
    """View for managing all ability scores."""
    def __init__(self, user_id: str, points_remaining: int):
        super().__init__()
        self.user_id = user_id
        self.points_remaining = points_remaining
        self.abilities = ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma']
        
        for ability in self.abilities:
            self.add_item(AbilityButton(ability, user_id, points_remaining))
        
        # Add finish button if all abilities are set
        session = session_manager.get_session(user_id)
        if session and all(ability in session.stats for ability in self.abilities):
            self.add_item(FinishAbilityScoresButton(user_id))


class AbilityButton(ui.Button):
    """Button for setting an individual ability score."""
    def __init__(self, ability_name: str, user_id: str, points_remaining: int):
        session = session_manager.get_session(user_id)
        current_value = session.stats.get(ability_name, 'Not Set') if session else 'Not Set'
        
        super().__init__(
            label=f"{ability_name}: {current_value}",
            style=discord.ButtonStyle.primary,
            custom_id=f"ability_{ability_name}"
        )
        self.ability_name = ability_name
        self.user_id = user_id
        self.points_remaining = points_remaining

    async def callback(self, interaction: discord.Interaction):
        """Show the modal for setting this ability score."""
        try:
            await interaction.response.send_modal(
                AbilityScoreModal(self.user_id, self.ability_name, self.points_remaining)
            )
        except Exception as e:
            logging.error(f"Error showing ability score modal: {e}")
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )

class FinishAbilityScoresButton(ui.Button):
    """Button for completing ability score assignment."""
    def __init__(self, user_id: str):
        super().__init__(
            label="Finish",
            style=discord.ButtonStyle.success,
            custom_id="finish_abilities"
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        """Complete ability score assignment and move to next step."""
        try:
            session = session_manager.get_session(self.user_id)
            if not session:
                await interaction.response.send_message(
                    "Session expired. Please start character creation again.",
                    ephemeral=True
                )
                return

            # Validate all abilities are set
            required_abilities = ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma']
            if not all(ability in session.stats for ability in required_abilities):
                await interaction.response.send_message(
                    "Please set all ability scores before continuing.",
                    ephemeral=True
                )
                return

            # Import view for next step
            from .views import PhysicalAbilitiesView
            await interaction.response.edit_message(
                content="Ability scores set! Let's continue with your character creation.",
                view=PhysicalAbilitiesView(self.user_id, session.area_lookup)
            )
            
            logging.info(f"User {self.user_id} completed ability score assignment")
            
        except Exception as e:
            logging.error(f"Error finishing ability scores: {e}")
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )



class PhysicalAbilitiesView(ui.View):
    """View for assigning physical ability scores."""
    def __init__(self, user_id: str, area_lookup: Dict[str, Any]):
        """Initialize the view.
        
        Args:
            user_id (str): Discord user ID
            area_lookup (Dict[str, Any]): Area data for the character
        """
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.physical_abilities = ['Strength', 'Dexterity', 'Constitution']
        
        session = session_manager.get_session(user_id)
        if not session:
            session = session_manager.create_session(user_id)
            
        for ability in self.physical_abilities:
            current_score = session.stats.get(ability, None)
            self.add_item(AbilitySelect(user_id, ability, current_score))
            
        # Import button after view definition to avoid circular import
        from .buttons import NextMentalAbilitiesButton
        self.add_item(NextMentalAbilitiesButton(user_id, area_lookup))
        logging.info(f"PhysicalAbilitiesView created for user {user_id} with {len(self.children)} components.")

class MentalAbilitiesView(ui.View):
    """View for assigning mental ability scores."""
    def __init__(self, user_id: str, area_lookup: Dict[str, Any]):
        """Initialize the view.
        
        Args:
            user_id (str): Discord user ID
            area_lookup (Dict[str, Any]): Area data for the character
        """
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.mental_abilities = ['Intelligence', 'Wisdom', 'Charisma']
        
        session = session_manager.get_session(user_id)
        if not session:
            session = session_manager.create_session(user_id)
            
        for ability in self.mental_abilities:
            current_score = session.stats.get(ability, None)
            self.add_item(AbilitySelect(user_id, ability, current_score))
            
        # Import buttons after view definition to avoid circular import
        from .buttons import BackPhysicalAbilitiesButton, FinishAssignmentButton
        self.add_item(BackPhysicalAbilitiesButton(user_id))
        self.add_item(FinishAssignmentButton(user_id, self.area_lookup))
        logging.info(f"MentalAbilitiesView created for user {user_id} with {len(self.children)} components.")