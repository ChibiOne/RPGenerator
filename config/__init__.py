# config/__init__.py
from .settings import (
    DISCORD_BOT_TOKEN,
    OPENAI_API_KEY,
    DISCORD_APP_ID,
    REDIS_CONFIG,
    GUILD_CONFIGS,
    DEFAULT_STARTING_AREA,
    GLOBAL_COOLDOWN,
    CACHE_DURATION
)
from .logging_config import setup_logging

# Initialize logging when config is imported
loggers = setup_logging()

__all__ = [
    'DISCORD_BOT_TOKEN',
    'OPENAI_API_KEY',
    'DISCORD_APP_ID',
    'REDIS_CONFIG',
    'GUILD_CONFIGS',
    'DEFAULT_STARTING_AREA',
    'GLOBAL_COOLDOWN',
    'CACHE_DURATION',
    'setup_logging',
    'loggers'
]