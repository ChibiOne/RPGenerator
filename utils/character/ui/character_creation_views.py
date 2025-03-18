"""Character creation specific view classes.
Handles the UI flow for character creation process.
"""
import logging
import discord
from discord import ui
from typing import List, Optional, Dict, Any

from ..session import session_manager
from .dropdowns import GenericDropdown
from .embeds import create_character_progress_embed

class GenderSelectionView(ui.View):
    """View for gender selection using a dropdown."""
    def __init__(self, user_id: str):
        super().__init__()
        options = [
            discord.SelectOption(label="Male", description="Male gender"),
            discord.SelectOption(label="Female", description="Female gender"),
            discord.SelectOption(label="Non-binary", description="Non-binary gender"),
            discord.SelectOption(label="Other", description="Other or unspecified gender"),
        ]
        
        async def gender_callback(interaction: discord.Interaction, user_id: str, selected_value: str) -> None:
            """Handle gender selection."""
            session = session_manager.get_session(user_id)
            if not session:
                session = session_manager.create_session(user_id)
            
            session.gender = selected_value
            embed = create_character_progress_embed(user_id, 2)
            
            from .views import PronounsSelectionView  # Lazy import to avoid circular dependency
            await interaction.response.edit_message(
                content=f"Gender set to {selected_value}! Please choose your pronouns:",
                embed=embed,
                view=PronounsSelectionView(user_id)
            )
            logging.info(f"User {user_id} selected gender: {selected_value}")
            
        self.add_item(GenericDropdown(
            placeholder="Choose your character's gender...",
            options=options,
            callback_func=gender_callback,
            user_id=user_id
        ))

class PronounsSelectionView(ui.View):
    """View for pronouns selection using a dropdown."""
    def __init__(self, user_id: str):
        super().__init__()
        options = [
            discord.SelectOption(label="He/Him", description="He/Him pronouns"),
            discord.SelectOption(label="She/Her", description="She/Her pronouns"),
            discord.SelectOption(label="They/Them", description="They/Them pronouns"),
            discord.SelectOption(label="Other", description="Other pronouns"),
        ]
        
        async def pronouns_callback(interaction: discord.Interaction, user_id: str, selected_value: str) -> None:
            """Handle pronouns selection."""
            session = session_manager.get_session(user_id)
            if not session:
                session = session_manager.create_session(user_id)
                
            session.pronouns = selected_value
            embed = create_character_progress_embed(user_id, 3)
            
            from .modals import DescriptionModal  # Lazy import to avoid circular dependency
            await interaction.response.send_modal(DescriptionModal(user_id))
            logging.info(f"User {user_id} selected pronouns: {selected_value}")
            
        self.add_item(GenericDropdown(
            placeholder="Choose your character's pronouns...",
            options=options,
            callback_func=pronouns_callback,
            user_id=user_id
        ))

class SpeciesSelectionView(ui.View):
    """View for species selection using a dropdown."""
    def __init__(self, user_id: str):
        super().__init__()
        options = [
            discord.SelectOption(label="Human", description="A versatile and adaptable species."),
            discord.SelectOption(label="Elf", description="Graceful and attuned to magic."),
            discord.SelectOption(label="Dwarf", description="Sturdy and resilient."),
            discord.SelectOption(label="Orc", description="Strong and fierce."),
        ]
        
        async def species_callback(interaction: discord.Interaction, user_id: str, selected_value: str) -> None:
            """Handle species selection."""
            session = session_manager.get_session(user_id)
            if not session:
                session = session_manager.create_session(user_id)
                
            session.species = selected_value
            embed = create_character_progress_embed(user_id, 5)
            await interaction.response.edit_message(
                content=f"Species set to {selected_value}! Please choose your class:",
                embed=embed,
                view=ClassSelectionView(user_id)
            )
            logging.info(f"User {user_id} selected species: {selected_value}")
            
        self.add_item(GenericDropdown(
            placeholder="Choose your species...",
            options=options,
            callback_func=species_callback,
            user_id=user_id
        ))

class ClassSelectionView(ui.View):
    """View for class selection using a dropdown."""
    def __init__(self, user_id: str):
        super().__init__()
        options = [
            discord.SelectOption(label="Warrior", description="A strong fighter."),
            discord.SelectOption(label="Mage", description="A wielder of magic."),
            discord.SelectOption(label="Rogue", description="A stealthy character."),
            discord.SelectOption(label="Cleric", description="A healer and protector."),
        ]
        
        async def class_callback(interaction: discord.Interaction, user_id: str, selected_value: str) -> None:
            """Handle class selection."""
            session = session_manager.get_session(user_id)
            if not session:
                session = session_manager.create_session(user_id)
                
            session.char_class = selected_value
            embed = create_character_progress_embed(user_id, 6)
            
            from .views import PhysicalAbilitiesView  # Lazy import to avoid circular dependency
            await interaction.response.edit_message(
                content="Please confirm your character's initial details:",
                embed=embed,
                view=PhysicalAbilitiesView(user_id, session_manager.get_session(user_id).area_lookup)
            )
            logging.info(f"User {user_id} selected class: {selected_value}")
            
        self.add_item(GenericDropdown(
            placeholder="Choose your class...",
            options=options,
            callback_func=class_callback,
            user_id=user_id
        ))
