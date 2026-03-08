import logging
from logging.handlers import RotatingFileHandler
import os

# Create logs directory if it doesn't exist (optional, we'll just put it in root for simplicity as planned)
LOG_FILE = "app.log"

def setup_logger(name: str) -> logging.Logger:
    """
    Sets up a scalable rotating file logger.
    - Writes to app.log
    - Max size 5MB before rotating.
    - Keeps up to 3 older backup logs.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if setup_logger is called multiple times for the same module
    if not logger.handlers:
        # Rotating File Handler
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3
        )
        file_handler.setLevel(logging.INFO)

        # Standard Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

# Create a default app logger instance easily importable from anywhere
app_logger = setup_logger("shailoom_api")
