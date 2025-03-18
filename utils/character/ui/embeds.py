# utils/character/ui/embeds.py
import discord
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...game_objects import Character

from ..constants import POINT_BUY_TOTAL
from ..session import session_manager

def create_character_embed(character: 'Character') -> discord.Embed:
    """Creates an embed displaying character information.
    
    Args:
        character (Character): The character to display
        
    Returns:
        discord.Embed: The character information embed
    """
    try:
        embed = discord.Embed(
            title=f"Character: {character.name}",
            color=discord.Color.blue()
        )
        
        # Basic Info
        basic_info = [
            f"**Species:** {character.species}",
            f"**Class:** {character.char_class}",
            f"**Gender:** {character.gender}",
            f"**Pronouns:** {character.pronouns}"
        ]
        embed.add_field(
            name="Basic Information",
            value="\n".join(basic_info),
            inline=False
        )
        
        # Description
        if character.description:
            embed.add_field(
                name="Description",
                value=character.description[:1024],  # Discord field limit
                inline=False
            )
        
        # Stats
        stats_info = []
        for stat, value in character.stats.items():
            modifier = (value - 10) // 2
            sign = "+" if modifier >= 0 else ""
            stats_info.append(f"**{stat}:** {value} ({sign}{modifier})")
        
        embed.add_field(
            name="Ability Scores",
            value="\n".join(stats_info),
            inline=True
        )
        
        # Combat Stats
        combat_info = [
            f"**HP:** {character.curr_hp}/{character.max_hp}",
            f"**AC:** {character.ac}",
            f"**Movement:** {character.movement_speed} ft"
        ]
        embed.add_field(
            name="Combat Statistics",
            value="\n".join(combat_info),
            inline=True
        )
        
        # Equipment
        equipment_info = []
        for slot, item in character.equipment.items():
            if isinstance(item, list):  # For slots like Belt_Slots
                items = [i.name if i else "Empty" for i in item]
                equipment_info.append(f"**{slot}:** {', '.join(items)}")
            else:  # For single item slots
                item_name = item.name if item else "Empty"
                equipment_info.append(f"**{slot}:** {item_name}")
                
        embed.add_field(
            name="Equipment",
            value="\n".join(equipment_info) if equipment_info else "No equipment",
            inline=False
        )
        
        # Location
        location_info = [
            f"**Area:** {character.current_area.name if character.current_area else 'Unknown'}",
            f"**Location:** {character.current_location}",
            f"**Region:** {character.current_region}",
            f"**Continent:** {character.current_continent}"
        ]
        embed.add_field(
            name="Current Location",
            value="\n".join(location_info),
            inline=False
        )
        
        # Add character level and XP if applicable
        if hasattr(character, 'level') and hasattr(character, 'xp'):
            embed.add_field(
                name="Progression",
                value=f"**Level:** {character.level}\n**XP:** {character.xp}",
                inline=True
            )
        
        return embed
        
    except Exception as e:
        logging.error(f"Error creating character embed: {e}")
        return discord.Embed(
            title="Error",
            description="Could not display character information.",
            color=discord.Color.red()
        )

def create_character_progress_embed(user_id: str, step: int) -> discord.Embed:
    """Creates an embed showing character creation progress.
    
    Args:
        user_id (str): The user's ID
        step (int): Current step in character creation (1-6)
        
    Returns:
        discord.Embed: The progress embed
    """
    session = session_manager.get_session(user_id)
    if not session:
        session = session_manager.create_session(user_id)

    embed = discord.Embed(title="Character Creation Progress", color=discord.Color.blue())
    
    steps = {
        1: ("Name", session.name),
        2: ("Gender", session.gender),
        3: ("Pronouns", session.pronouns),
        4: ("Description", "Set" if session.description else "Not Set"),
        5: ("Species", session.species),
        6: ("Class", session.char_class)
    }
    
    for s, (label, value) in steps.items():
        status = "✅" if value else "❌"
        marker = "➡️" if s == step else ""
        embed.add_field(
            name=f"{marker} Step {s}: {label}",
            value=f"{status} {value if value else 'Not Set'}",
            inline=False
        )
    
    return embed

def generate_ability_embed(user_id: str) -> Optional[discord.Embed]:
    """Generates an embed reflecting the current ability scores and remaining points.
    
    Args:
        user_id (str): The user's ID
        
    Returns:
        Optional[discord.Embed]: The ability scores embed or None if error
    """
    try:
        session = session_manager.get_session(user_id)
        if not session:
            session = session_manager.create_session(user_id)
            
        remaining_points = POINT_BUY_TOTAL - session.points_spent

        embed = discord.Embed(
            title="Character Creation - Ability Scores",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Remaining Points",
            value=f"{remaining_points}/{POINT_BUY_TOTAL}",
            inline=False
        )

        for ability in ['Strength', 'Dexterity', 'Constitution',
                       'Intelligence', 'Wisdom', 'Charisma']:
            score = session.stats.get(ability, 10)
            embed.add_field(name=ability, value=str(score), inline=True)

        embed.set_footer(text="Assign your ability scores using the dropdowns below.")

        return embed
    except Exception as e:
        logging.error(f"Error generating ability embed for user {user_id}: {e}")
        return None

async def update_embed(interaction: discord.Interaction, user_id: str) -> None:
    """Updates the embed in the original message to reflect the current state.
    
    Args:
        interaction (discord.Interaction): The interaction to respond to
        user_id (str): The user's ID
    """
    embed = generate_ability_embed(user_id)
    if embed:
        await interaction.message.edit(embed=embed)
        logging.info(f"Embed updated for user {user_id}.")
    else:
        logging.error(f"Failed to update embed for user {user_id}.")

__all__ = [
    'create_character_embed',
    'create_character_progress_embed',
    'generate_ability_embed',
    'update_embed'
]