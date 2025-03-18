"""UI button components for character creation and management."""
import logging
import discord
from typing import Dict, Any, Optional

from ..constants import POINT_BUY_TOTAL
from ..session import session_manager
from ..validators import is_valid_point_allocation
from ..callbacks.character import finalize_character

from .modals import CharacterNameModal
from .embeds import generate_ability_embed

class ConfirmButton(discord.ui.Button):
    """Generic confirmation button."""
    def __init__(self, callback_func=None):
        """Initialize the button.
        
        Args:
            callback_func (Optional[Callable]): Custom callback function
        """
        super().__init__(
            label="Confirm",
            style=discord.ButtonStyle.success,
            custom_id="confirm_button"
        )
        self._callback_func = callback_func

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle button click."""
        try:
            if self._callback_func:
                await self._callback_func(interaction)
            else:
                await interaction.response.edit_message(content="Confirmed!", view=None)
        except Exception as e:
            logging.error(f"Error in ConfirmButton callback: {e}")
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )

class CancelButton(discord.ui.Button):
    """Generic cancel button."""
    def __init__(self, callback_func=None):
        """Initialize the button.
        
        Args:
            callback_func (Optional[Callable]): Custom callback function
        """
        super().__init__(
            label="Cancel",
            style=discord.ButtonStyle.danger,
            custom_id="cancel_button"
        )
        self._callback_func = callback_func

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle button click."""
        try:
            if self._callback_func:
                await self._callback_func(interaction)
            else:
                await interaction.response.edit_message(content="Cancelled.", view=None)
        except Exception as e:
            logging.error(f"Error in CancelButton callback: {e}")
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )

class StartCharacterButton(discord.ui.Button):
    """Button to initiate character creation."""
    def __init__(self, bot):
        super().__init__(label="Start Character Creation", style=discord.ButtonStyle.green)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle button click.
        
        Args:
            interaction (discord.Interaction): The interaction that triggered this callback
        """
        try:
            user_id = str(interaction.user.id)
            session = session_manager.get_session(user_id)
            if not session:
                session = session_manager.create_session(user_id)

            # Present the modal to get the character's name
            await interaction.response.send_modal(CharacterNameModal(user_id))
            
        except Exception as e:
            logging.error(f"Error in StartCharacterButton callback for user {user_id}: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An error occurred. Please try again.",
                    ephemeral=True
                )

class NextMentalAbilitiesButton(discord.ui.Button):
    """Button to proceed to mental abilities."""
    def __init__(self, user_id: str, area_lookup: Dict[str, Any]):
        super().__init__(label="Next", style=discord.ButtonStyle.blurple)
        self.user_id = user_id
        self.area_lookup = area_lookup

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle button click."""
        try:
            session = session_manager.get_session(self.user_id)
            if not session:
                session = session_manager.create_session(self.user_id)
                
            if session.points_spent > POINT_BUY_TOTAL:
                await interaction.response.send_message(
                    f"You have overspent your points by **{session.points_spent - POINT_BUY_TOTAL}** points. "
                    "Please adjust your ability scores.",
                    ephemeral=True
                )
                logging.warning(f"User {self.user_id} overspent points before navigating to MentalAbilitiesView.")
                return

            # Import view here to avoid circular dependency
            from .abilities_view import MentalAbilitiesView
            
            # Generate the updated embed
            embed = generate_ability_embed(self.user_id)

            # Update the message
            await interaction.response.edit_message(
                content="Now, please assign your mental abilities:",
                view=MentalAbilitiesView(self.user_id, self.area_lookup),
                embed=embed  
            )
            logging.info(f"User {self.user_id} navigated to MentalAbilitiesView.")
            
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )
            logging.error(f"Error in NextMentalAbilitiesButton callback for user {self.user_id}: {e}")

class BackPhysicalAbilitiesButton(discord.ui.Button):
    """Button to return to physical abilities."""
    def __init__(self, user_id: str):
        super().__init__(label="Back", style=discord.ButtonStyle.gray)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle button click."""
        try:
            # Import view here to avoid circular dependency
            from .abilities_view import PhysicalAbilitiesView
            
            # Generate the updated embed
            embed = generate_ability_embed(self.user_id)

            # Get view's area_lookup from session
            session = session_manager.get_session(self.user_id)
            if not session:
                raise ValueError("Session not found")
                
            area_lookup = session.area_lookup

            # Return to physical abilities
            await interaction.response.edit_message(
                content="Returning to Physical Abilities assignment:",
                view=PhysicalAbilitiesView(self.user_id, area_lookup),
                embed=embed 
            )
            logging.info(f"User {self.user_id} navigated back to PhysicalAbilitiesView.")
            
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )
            logging.error(f"Error in BackPhysicalAbilitiesButton callback for user {self.user_id}: {e}")

class FinishAssignmentButton(discord.ui.Button):
    """Button to complete ability score assignment."""
    def __init__(self, user_id: str, area_lookup: Dict[str, Any]):
        super().__init__(label="Finish", style=discord.ButtonStyle.green)
        self.user_id = user_id
        self.area_lookup = area_lookup

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle button click."""
        try:
            session = session_manager.get_session(self.user_id)
            if not session:
                raise ValueError("Session not found")
                
            is_valid, message = is_valid_point_allocation(session.stats)
            if not is_valid:
                await interaction.response.send_message(
                    f"Point allocation error: {message}. Please adjust your scores before finalizing.",
                    ephemeral=True
                )
                logging.warning(f"User {self.user_id} failed point allocation validation: {message}")
                return

            # Import view here to avoid circular dependency
            from .finalize_views import FinalizeCharacterView
            
            # Generate the updated embed
            embed = generate_ability_embed(self.user_id)

            await interaction.response.edit_message(
                content="All ability scores have been assigned correctly. Click the button below to finish.",
                view=FinalizeCharacterView(self.user_id, self.area_lookup),
                embed=embed 
            )
            logging.info(f"User {self.user_id} prepared to finalize character creation.")
            
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )
            logging.error(f"Error in FinishAssignmentButton callback for user {self.user_id}: {e}")

class FinalizeCharacterButton(discord.ui.Button):
    """Button to complete character creation."""
    def __init__(self, user_id: str, area_lookup: Dict[str, Any]):
        super().__init__(label="Finish Character Creation", style=discord.ButtonStyle.green)
        self.user_id = user_id
        self.area_lookup = area_lookup

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle button click."""
        try:
            # Verify session exists
            session = session_manager.get_session(self.user_id)
            if not session:
                session = session_manager.create_session(self.user_id)

            # Validate ability scores
            is_valid, message = is_valid_point_allocation(session.stats)
            if not is_valid:
                await interaction.response.send_message(
                    f"Character creation failed: {message}",
                    ephemeral=True
                )
                logging.warning(f"User {self.user_id} failed point allocation validation during finalization: {message}")
                return

            # Create the character
            character = await finalize_character(interaction, self.user_id, self.area_lookup)
            if not character:
                await interaction.response.send_message(
                    "Character creation failed. Please try again.",
                    ephemeral=True
                )
                logging.error(f"Character creation failed for user {self.user_id}.")
                return
                
            # Create summary embed
            embed = discord.Embed(
                title=f"Character '{character.name}' Created!",
                color=discord.Color.green()
            )
            
            # Add character details
            embed.add_field(name="Species", value=character.species, inline=True)
            embed.add_field(name="Class", value=character.char_class, inline=True)
            embed.add_field(name="Gender", value=character.gender, inline=True)
            embed.add_field(name="Pronouns", value=character.pronouns, inline=True)
            embed.add_field(name="Description", value=character.description, inline=False)
            
            # Add stats
            stats_text = "\n".join(f"{stat}: {value}" for stat, value in character.stats.items())
            embed.add_field(name="Stats", value=stats_text, inline=True)
            
            # Add equipment
            equipment_text = []
            for slot, item in character.equipment.items():
                if isinstance(item, list):
                    # Handle multi-item slots
                    items = [i.Name if hasattr(i, 'Name') else 'Empty' for i in item if i is not None]
                    equipment_text.append(f"{slot}: {', '.join(items) if items else 'Empty'}")
                else:
                    # Handle single item slots
                    item_name = item.Name if item and hasattr(item, 'Name') else 'Empty'
                    equipment_text.append(f"{slot}: {item_name}")
            embed.add_field(name="Equipment", value="\n".join(equipment_text), inline=True)
            
            # Add inventory
            if character.inventory:
                inventory_text = []
                for item_key, item in character.inventory.items():
                    if hasattr(item, 'Name'):
                        inventory_text.append(item.Name)
                    elif isinstance(item, dict) and 'Name' in item:
                        inventory_text.append(item['Name'])
                inventory_display = "\n".join(inventory_text) if inventory_text else "Empty"
            else:
                inventory_display = "Empty"
            embed.add_field(name="Inventory", value=inventory_display, inline=True)

            # Send completion message
            await interaction.response.edit_message(
                content="Your character has been created successfully!",
                view=None,
                embed=embed
            )
            logging.info(f"Character '{character.name}' created successfully for user {self.user_id}.")
            
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )
            logging.error(f"Error in FinalizeCharacterButton callback for user {self.user_id}: {e}")

# Export components
__all__ = [
    'StartCharacterButton',
    'NextMentalAbilitiesButton',
    'BackPhysicalAbilitiesButton',
    'FinishAssignmentButton',
    'FinalizeCharacterButton',
    'ConfirmButton',
    'CancelButton'
]