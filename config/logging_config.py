# config/logging_config.py
import logging
import logging.handlers
from pathlib import Path

def setup_logging(log_dir: str = "logs") -> None:
    """
    Configure logging for the application.
    
    Args:
        log_dir: Directory to store log files, defaults to "logs"
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Configure logging format
    log_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d:%(funcName)s - %(message)s'
    )
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "bot.log",
        maxBytes=5_242_880,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_format)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Create loggers for different components
    loggers = {
        'bot': logging.getLogger('bot'),
        'character': logging.getLogger('character'),
        'world': logging.getLogger('world'),
        'redis': logging.getLogger('redis'),
        'events': logging.getLogger('events')
    }
    
    # Set levels for specific loggers if needed
    loggers['redis'].setLevel(logging.WARNING)  # Example: Less verbose Redis logs
    
    return loggers