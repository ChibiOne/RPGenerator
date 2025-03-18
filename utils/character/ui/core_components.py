"""Core UI components shared across multiple views."""
import logging
import discord
from discord import ui
from typing import Optional, Dict, Any, List, Union, Callable

from ..session import session_manager
from ..constants import POINT_BUY_TOTAL, ABILITY_SCORE_COSTS

class AbilitySelect(ui.Select):
    """Dropdown for selecting an ability score.
    
    Attributes:
        user_id (str): The Discord user ID
        ability_name (str): The name of the ability being set
    """
    def __init__(self, user_id: str, ability_name: str, current_score: Optional[int] = None):
        """Initialize the ability score selector.
        
        Args:
            user_id (str): Discord user ID
            ability_name (str): Name of the ability (e.g., 'Strength')
            current_score (Optional[int]): Current score, if any
        """
        self.user_id = user_id
        self.ability_name = ability_name
        
        options = [
            discord.SelectOption(label="8", description="Gain 2 points", default=(current_score == 8)),
            discord.SelectOption(label="9", description="Gain 1 point", default=(current_score == 9)),
            discord.SelectOption(label="10", description="0 points", default=(current_score == 10)),
            discord.SelectOption(label="11", description="Spend 1 point", default=(current_score == 11)),
            discord.SelectOption(label="12", description="Spend 2 points", default=(current_score == 12)),
            discord.SelectOption(label="13", description="Spend 3 points", default=(current_score == 13)),
            discord.SelectOption(label="14", description="Spend 5 points", default=(current_score == 14)),
            discord.SelectOption(label="15", description="Spend 7 points", default=(current_score == 15)),
        ]
        
        placeholder_text = f"{self.ability_name}: {current_score}" if current_score is not None else f"Assign {ability_name} score..."
        
        super().__init__(
            placeholder=placeholder_text,
            min_values=1,
            max_values=1,
            options=options
        )
        logging.info(f"AbilitySelect initialized for {ability_name} with current_score={current_score}.")

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle ability score selection.
        
        Args:
            interaction (discord.Interaction): The interaction that triggered this callback
        """
        try:
            selected_score = int(self.values[0])
            
            session = session_manager.get_session(self.user_id)
            if not session:
                session = session_manager.create_session(self.user_id)
            
            # Get previous score and costs
            previous_score = session.stats.get(self.ability_name, 10)
            previous_cost = ABILITY_SCORE_COSTS.get(previous_score, 0)
            new_cost = ABILITY_SCORE_COSTS.get(selected_score, 0)
            
            # Update points spent
            points_delta = new_cost - previous_cost
            new_points_spent = session.points_spent + points_delta
            
            if new_points_spent > POINT_BUY_TOTAL:
                await interaction.response.send_message(
                    f"Insufficient points to assign **{selected_score}** to **{self.ability_name}**. "
                    f"You have **{POINT_BUY_TOTAL - session.points_spent} points** remaining.",
                    ephemeral=True
                )
                logging.warning(f"User {self.user_id} attempted to overspend points on {self.ability_name}.")
                return
            
            # Update session
            session.stats[self.ability_name] = selected_score
            session.points_spent = new_points_spent
            
            # Import views here to avoid circular dependency
            from .abilities_view import PhysicalAbilitiesView, MentalAbilitiesView
            
            # Update UI based on view type
            if isinstance(self.view, PhysicalAbilitiesView):
                new_view = PhysicalAbilitiesView(self.user_id, self.view.area_lookup)
            elif isinstance(self.view, MentalAbilitiesView):
                new_view = MentalAbilitiesView(self.user_id, self.view.area_lookup)
            else:
                new_view = self.view
                logging.warning(f"Unknown view type for user {self.user_id}: {type(self.view)}")
            
            # Generate updated embed
            from .embeds import generate_ability_embed
            embed = generate_ability_embed(self.user_id)
            if not embed:
                raise ValueError("Failed to generate ability embed")
            
            # Update the message
            await interaction.response.edit_message(
                view=new_view,
                embed=embed
            )
            logging.info(
                f"Updated {self.ability_name} to {selected_score} for user {self.user_id}. "
                f"Points spent: {session.points_spent}/{POINT_BUY_TOTAL}"
            )
            
        except ValueError as e:
            error_msg = str(e) or f"Invalid input for {self.ability_name}. Please select a valid score."
            await interaction.response.send_message(error_msg, ephemeral=True)
            logging.error(
                f"ValueError in AbilitySelect callback for {self.ability_name}, "
                f"user {self.user_id}: {e}"
            )
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred while updating your ability score. Please try again.",
                ephemeral=True
            )
            logging.error(
                f"Error in AbilitySelect callback for {self.ability_name}, "
                f"user {self.user_id}: {e}",
                exc_info=True
            )

class GenericDropdown(ui.Select):
    """Generic dropdown component with callback function support.
    
    Attributes:
        user_id (str): The Discord user ID
        callback_func (Callable): The function to call when an option is selected
    """
    def __init__(self, *, placeholder: str, options: List[discord.SelectOption],
                callback_func: Callable[[discord.Interaction, str, str], None],
                user_id: str) -> None:
        """Initialize the dropdown.
        
        Args:
            placeholder (str): Text to show when nothing is selected
            options (List[discord.SelectOption]): List of dropdown options
            callback_func (Callable): Function to call when an option is selected
            user_id (str): Discord user ID
        """
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options
        )
        self.callback_func = callback_func
        self.user_id = user_id
        
    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle dropdown selection.
        
        Args:
            interaction (discord.Interaction): The interaction that triggered this callback
        """
        try:
            await self.callback_func(interaction, self.user_id, self.values[0])
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred processing your selection. Please try again.",
                ephemeral=True
            )
            logging.error(
                f"Error in GenericDropdown callback for user {self.user_id}: {e}",
                exc_info=True
            )