# utils/character/callbacks/ability.py
import logging
import discord
from typing import Dict, Any, Optional

from ..session import session_manager
from ..constants import POINT_BUY_TOTAL
from ..ui.views import PhysicalAbilitiesView

async def start_ability_score_assignment(interaction: discord.Interaction, user_id: str):
    """Start the ability score assignment process for a character.
    
    Args:
        interaction (discord.Interaction): The Discord interaction
        user_id (str): The user's Discord ID
    """
    try:
        session = session_manager.get_session(user_id)
        if not session:
            await interaction.response.send_message(
                "Session expired. Please start character creation again.",
                ephemeral=True
            )
            return

        area_lookup = session.area_lookup

        await interaction.response.edit_message(
            content="Let's begin your character creation!\n\n"
            f"You have **{POINT_BUY_TOTAL} points** to distribute among your abilities using the point-buy system.\n\n"
            "Here's how the costs work:\n"
            "- **8:** Gain 2 points\n"
            "- **9:** Gain 1 point\n"
            "- **10:** 0 points\n"
            "- **11:** Spend 1 point\n"
            "- **12:** Spend 2 points\n"
            "- **13:** Spend 3 points\n"
            "- **14:** Spend 5 points\n"
            "- **15:** Spend 7 points\n\n"
            "No ability score can be raised above **15**, and none can be lowered below **8**.\n\n"
            "Please assign your **Physical Attributes**:",
            view=PhysicalAbilitiesView(user_id, area_lookup)
        )
        logging.info(f"Started ability score assignment for user {user_id}")
    except Exception as e:
        logging.error(f"Error starting ability score assignment for user {user_id}: {e}")
        await interaction.response.send_message(
            "An error occurred while starting ability score assignment. Please try again.",
            ephemeral=True
        )

async def process_ability_scores(interaction: discord.Interaction, user_id: str) -> bool:
    """Process and validate ability scores.
    
    Args:
        interaction (discord.Interaction): The Discord interaction
        user_id (str): The user's Discord ID
        
    Returns:
        bool: True if processing succeeded, False otherwise
    """
    try:
        session = session_manager.get_session(user_id)
        if not session:
            await interaction.response.send_message(
                "Session expired. Please start character creation again.",
                ephemeral=True
            )
            return False

        required_abilities = [
            'Strength', 'Dexterity', 'Constitution',
            'Intelligence', 'Wisdom', 'Charisma'
        ]

        # Verify all abilities are set
        missing_abilities = [
            ability for ability in required_abilities 
            if ability not in session.stats
        ]
        
        if missing_abilities:
            await interaction.response.send_message(
                f"Please set the following abilities before continuing: {', '.join(missing_abilities)}",
                ephemeral=True
            )
            return False

        # Verify point allocation
        points_spent = sum(
            calculate_point_cost(score)
            for score in session.stats.values()
        )

        if points_spent > POINT_BUY_TOTAL:
            await interaction.response.send_message(
                f"You have spent {points_spent} points, but only {POINT_BUY_TOTAL} are available. "
                "Please adjust your ability scores.",
                ephemeral=True
            )
            return False

        logging.info(f"Successfully processed ability scores for user {user_id}")
        return True

    except Exception as e:
        logging.error(f"Error processing ability scores for user {user_id}: {e}")
        await interaction.response.send_message(
            "An error occurred while processing ability scores. Please try again.",
            ephemeral=True
        )
        return False

def calculate_point_cost(score: int) -> int:
    """Calculate the point cost for an ability score.
    
    Args:
        score (int): The ability score value
        
    Returns:
        int: The point cost (negative for scores below 10)
    """
    costs = {
        8: -2,  # Gain 2 points
        9: -1,  # Gain 1 point
        10: 0,  # No cost
        11: 1,  # Spend 1 point
        12: 2,  # Spend 2 points
        13: 3,  # Spend 3 points
        14: 5,  # Spend 5 points
        15: 7   # Spend 7 points
    }
    return costs.get(score, 0)  # Return 0 for invalid scores as a safety default

__all__ = [
    'start_ability_score_assignment',
    'process_ability_scores',
    'calculate_point_cost'
]