"""Core UI views for the RPG system.
Handles character creation flow and ability score management.
"""
import logging
import discord
from discord import ui
from typing import Dict, Any

# Character creation flow views
from .character_creation_views import (
    GenderSelectionView,
    PronounsSelectionView,
    SpeciesSelectionView,
    ClassSelectionView
)

# Ability score views
from .abilities_view import PhysicalAbilitiesView, MentalAbilitiesView

# Finalization views
from .finalize_views import ConfirmationView, FinalizeCharacterView

# Core buttons
from .buttons import StartCharacterButton

class CharacterCreationView(ui.View):
    """Initial view for starting character creation."""
    def __init__(self, bot):
        """Initialize the view.
        
        Args:
            bot: The Discord bot instance
        """
        super().__init__()
        self.bot = bot
        self.add_item(StartCharacterButton(bot))
        logging.info("CharacterCreationView initialized")

# Export all views
__all__ = [
    'CharacterCreationView',
    'GenderSelectionView',
    'PronounsSelectionView',
    'SpeciesSelectionView',
    'ClassSelectionView',
    'PhysicalAbilitiesView',
    'MentalAbilitiesView',
    'ConfirmationView',
    'FinalizeCharacterView'
]