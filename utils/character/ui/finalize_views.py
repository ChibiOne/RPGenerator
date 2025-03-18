"""Views for finalizing character creation."""
import logging
import discord
from discord import ui
from typing import Dict, Any, Optional

from ..session import session_manager
from .abilities_view import MentalAbilitiesView

class ConfirmationView(ui.View):
    """View for confirming character creation choices."""
    def __init__(self, user_id: str, area_lookup: Dict[str, Any]):
        """Initialize the confirmation view.
        
        Args:
            user_id (str): Discord user ID
            area_lookup (Dict[str, Any]): Area data for the character
        """
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        self.add_item(discord.ui.Button(
            label="Confirm", 
            style=discord.ButtonStyle.green,
            custom_id="confirm"
        ))
        self.add_item(discord.ui.Button(
            label="Cancel", 
            style=discord.ButtonStyle.red,
            custom_id="cancel"
        ))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle button click.
        
        Args:
            interaction (discord.Interaction): The interaction that triggered this callback
        """
        try:
            if interaction.custom_id == "confirm":
                # Import here to avoid circular dependency
                from .buttons import finalize_character
                await finalize_character(interaction, self.user_id, self.area_lookup)
            else:
                await interaction.response.edit_message(
                    content="Returning to ability scores...",
                    view=MentalAbilitiesView(self.user_id, self.area_lookup)
                )
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred processing your selection. Please try again.",
                ephemeral=True
            )
            logging.error(
                f"Error in ConfirmationView callback for user {self.user_id}: {e}",
                exc_info=True
            )

class FinalizeCharacterView(ui.View):
    """View for final character creation step."""
    def __init__(self, user_id: str, area_lookup: Dict[str, Any]):
        """Initialize the finalize view.
        
        Args:
            user_id (str): Discord user ID
            area_lookup (Dict[str, Any]): Area data for the character
        """
        super().__init__()
        self.user_id = user_id
        self.area_lookup = area_lookup
        
        # Import here to avoid circular dependency
        from .buttons import FinalizeCharacterButton
        self.add_item(FinalizeCharacterButton(user_id, area_lookup))
        logging.info(f"FinalizeCharacterView created for user {user_id} with {len(self.children)} components.")

# Export components
__all__ = ['ConfirmationView', 'FinalizeCharacterView']