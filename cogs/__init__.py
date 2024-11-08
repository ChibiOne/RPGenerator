# cogs/__init__.py
from typing import List
from pathlib import Path
import logging

# Import core event handlers
from .events.bot_events import BotEvents
from .events.error_handler import ErrorHandler
from .events.message_handler import MessageHandler

# Import gameplay cogs
from .character.creation import CharacterCreation
from .travel import TravelSystem

# Setup logging
logger = logging.getLogger(__name__)

def setup(bot):
    """
    Setup function to load all cogs
    Args:
        bot: The bot instance
    """
    cogs = [
        BotEvents(bot),
        ErrorHandler(bot),
        MessageHandler(bot),
        CharacterCreation(bot),
        TravelSystem(bot)
    ]
    
    for cog in cogs:
        try:
            bot.add_cog(cog)
            logger.info(f"Loaded cog: {cog.__class__.__name__}")
        except Exception as e:
            logger.error(f"Failed to load cog {cog.__class__.__name__}: {str(e)}")
            raise

__all__ = [
    'BotEvents',
    'ErrorHandler',
    'MessageHandler',
    'CharacterCreation',
    'TravelSystem',
    'setup'
]