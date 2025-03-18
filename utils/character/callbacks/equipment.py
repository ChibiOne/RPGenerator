# utils/character/callbacks/equipment.py
import logging
import discord
from typing import Optional

from ..session import session_manager
from ..ui.embeds import create_character_progress_embed

async def process_equipment_selection(interaction: discord.Interaction, user_id: str) -> bool:
    """Process and validate equipment selection for character creation.
    
    Args:
        interaction (discord.Interaction): The Discord interaction
        user_id (str): The user's Discord ID
        
    Returns:
        bool: True if processing succeeded, False otherwise
    """
    try:
        # Get and validate session
        session = session_manager.get_session(user_id)
        if not session:
            await interaction.response.send_message(
                "Session expired. Please start character creation again.",
                ephemeral=True
            )
            return False

        if not session.char_class:
            await interaction.response.send_message(
                "Please select a class before proceeding with equipment.",
                ephemeral=True
            )
            return False

        # Get equipment manager from client
        equipment_manager = interaction.client.equipment_manager
        if not equipment_manager:
            logging.error("Equipment manager not found in client")
            await interaction.response.send_message(
                "Error accessing equipment system. Please try again.",
                ephemeral=True
            )
            return False

        # Get starting equipment
        equipment, inventory = equipment_manager.get_starting_equipment(session.char_class)
        
        # Validate equipment structure
        if not equipment_manager.validate_equipment(equipment):
            await interaction.response.send_message(
                "Error setting up starting equipment. Please try again.",
                ephemeral=True
            )
            return False

        # Update session with equipment and inventory
        session.equipment = equipment
        session.inventory = inventory

        # Create progress embed
        embed = create_character_progress_embed(user_id, 7)  # Equipment is step 7

        # Import view here to avoid circular dependency
        from ..ui.views import ConfirmationView
        
        await interaction.response.edit_message(
            content="Starting equipment assigned! Review and confirm your character:",
            embed=embed,
            view=ConfirmationView(user_id)
        )
        
        logging.info(f"Successfully processed equipment for user {user_id}")
        return True

    except Exception as e:
        logging.error(f"Error processing equipment for user {user_id}: {e}")
        await interaction.response.send_message(
            "An error occurred while processing equipment. Please try again.",
            ephemeral=True
        )
        return False

__all__ = [
    'process_equipment_selection'
]