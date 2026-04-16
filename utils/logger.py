"""
Logger module for GTNH Mod Installer
"""
import logging
from datetime import datetime
from typing import Optional, Callable


class Logger:
    """Simple logger with GUI callback support"""

    _instance: Optional['Logger'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.logger = logging.getLogger('GTNHModInstaller')
        self.logger.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # GUI callback
        self.gui_callback: Optional[Callable[[str], None]] = None

    def set_gui_callback(self, callback: Callable[[str], None]):
        """Set callback function for GUI log display"""
        self.gui_callback = callback

    def _log(self, level: int, message: str):
        self.logger.log(level, message)
        if self.gui_callback:
            timestamp = datetime.now().strftime('%H:%M:%S')
            level_name = logging.getLevelName(level)
            self.gui_callback(f"[{timestamp}] [{level_name}] {message}")

    def info(self, message: str):
        self._log(logging.INFO, message)

    def warning(self, message: str):
        self._log(logging.WARNING, message)

    def error(self, message: str):
        self._log(logging.ERROR, message)

    def debug(self, message: str):
        self._log(logging.DEBUG, message)

    def success(self, message: str):
        """Log a success message (displayed as info but with success indicator)"""
        self._log(logging.INFO, f"✓ {message}")


# Global logger instance
logger = Logger()
