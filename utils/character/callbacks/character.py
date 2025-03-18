# utils/character/callbacks/character.py
import logging
from typing import Optional, Dict, Any, cast
from datetime import datetime
import discord

from ..session import session_manager
from ...game_objects import Character
from ..validation import CharacterValidator
from ..types import (
    CharacterData,
    Stats,
    Equipment,
    SpeciesType,
    ClassType
)
from ..ui.embeds import create_character_progress_embed
from ..ui.views import GenderSelectionView

async def process_character_info(interaction: discord.Interaction, user_id: str) -> bool:
    """Process and validate basic character information.
    
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

        # Required fields
        required_fields = {
            'name': 'Name',
            'gender': 'Gender',
            'pronouns': 'Pronouns',
            'description': 'Description',
            'species': 'Species',
            'char_class': 'Class'
        }

        # Check for missing fields
        missing_fields = []
        for field, display_name in required_fields.items():
            if not getattr(session, field, None):
                missing_fields.append(display_name)

        if missing_fields:
            await interaction.response.send_message(
                f"Please complete the following fields before continuing: {', '.join(missing_fields)}",
                ephemeral=True
            )
            return False

        # Validate field lengths
        validation_rules = {
            'name': (2, 32),
            'description': (10, 1000)
        }

        for field, (min_len, max_len) in validation_rules.items():
            value = getattr(session, field)
            if len(value) < min_len or len(value) > max_len:
                await interaction.response.send_message(
                    f"The {field} must be between {min_len} and {max_len} characters long.",
                    ephemeral=True
                )
                return False

        # Validate allowed values
        if session.species not in ['Human', 'Elf', 'Dwarf', 'Orc']:
            await interaction.response.send_message(
                "Invalid species selected.",
                ephemeral=True
            )
            return False

        if session.char_class not in ['Warrior', 'Mage', 'Rogue', 'Cleric']:
            await interaction.response.send_message(
                "Invalid class selected.",
                ephemeral=True
            )
            return False

        logging.info(f"Successfully processed character info for user {user_id}")
        return True

    except Exception as e:
        logging.error(f"Error processing character info for user {user_id}: {e}")
        await interaction.response.send_message(
            "An error occurred while processing character information. Please try again.",
            ephemeral=True
        )
        return False

async def finalize_character(
    interaction: discord.Interaction,
    user_id: str,
    area_lookup: Dict[str, Any]
) -> Optional[Character]:
    """
    Finalizes character creation with strict validation and typing.
    
    Args:
        interaction: Discord interaction
        user_id: User's Discord ID
        area_lookup: Dictionary of available areas
    
    Returns:
        Optional[Character]: The created character or None if creation fails
    """
    try:
        # Get and validate session
        session = session_manager.get_session(user_id)
        if not session:
            logging.error(f"No session found for user {user_id}")
            return None

        # Create timestamp
        current_time = datetime.utcnow()
            
        # Construct character data with strict typing
        character_data: CharacterData = {
            "user_id": user_id,
            "name": session.name,
            "species": cast(SpeciesType, session.species),
            "char_class": cast(ClassType, session.char_class),
            "gender": session.gender,
            "pronouns": session.pronouns,
            "description": session.description,
            "stats": cast(Stats, session.stats),
            "equipment": cast(Equipment, session.equipment),
            "inventory": session.inventory,
            "creation_date": current_time,
            "last_modified": current_time,
            "last_interaction_guild": interaction.guild_id if interaction.guild else None
        }

        # Validate all data
        is_valid, message = CharacterValidator.validate_all(character_data)
        if not is_valid:
            logging.error(f"Character validation failed for user {user_id}: {message}")
            return None

        # Create character instance
        character = Character(**character_data)

        # Attempt to save to database
        try:
            if hasattr(interaction.client, 'redis_player'):
                # Start transaction
                async with interaction.client.redis_player.pipeline() as pipe:
                    # Save character
                    await pipe.set(f"character:{user_id}", character.to_dict())
                    # Save user-character mapping
                    await pipe.sadd(f"user:{user_id}:characters", character.name)
                    # Save guild mapping if applicable
                    if interaction.guild_id:
                        await pipe.sadd(f"guild:{interaction.guild_id}:characters", 
                                      f"{user_id}:{character.name}")
                    # Execute transaction
                    await pipe.execute()

                # Verify save
                saved_data = await interaction.client.redis_player.get(f"character:{user_id}")
                if not saved_data:
                    logging.error(f"Failed to verify character save for user {user_id}")
                    return None

                logging.info(f"Character saved successfully for user {user_id}")

            else:
                logging.error("Redis connection not available")
                return None

        except Exception as e:
            logging.error(f"Database error saving character for user {user_id}: {e}")
            return None

        # End the session
        session_manager.end_session(user_id)
        
        logging.info(f"Character creation successful for user {user_id}")
        return character

    except Exception as e:
        logging.error(f"Error finalizing character for user {user_id}: {e}", exc_info=True)
        return None

async def gender_callback(dropdown, interaction, user_id):
    """
    Callback for gender selection.
    
    Args:
        dropdown: Discord dropdown component
        interaction: Discord interaction
        user_id: User's Discord ID
    """
    try:
        session = session_manager.get_session(user_id)
        if not session:
            session = session_manager.create_session(user_id)
            
        selected_gender = dropdown.values[0]
        session.gender = selected_gender
        
        # Create progress embed
        embed = create_character_progress_embed(user_id, 2)
        
        await interaction.response.edit_message(
            content=f"Please select your pronouns:",
            embed=embed,
            view=PronounsSelectionView(user_id)
        )
        
        logging.info(f"User {user_id} selected gender: {selected_gender}")
    except Exception as e:
        logging.error(f"Error in gender_callback for user {user_id}: {e}")
        await interaction.response.send_message(
            "An error occurred. Please try again.",
            ephemeral=True
        )

__all__ = [
    'process_character_info',
    'finalize_character',
    'gender_callback'
]