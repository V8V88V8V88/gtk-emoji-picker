"""Pynput global hotkey listener backend for X11."""

import logging
import os
from collections.abc import Callable
from typing import Any

from gtk_emoji_picker.infrastructure.shortcut_backends.base import BaseShortcutListener

logger = logging.getLogger(__name__)


class PynputShortcutListener(BaseShortcutListener):
    """Global shortcut listener implementation using pynput.keyboard."""

    def __init__(self, shortcut: str = "Meta+.") -> None:
        super().__init__(shortcut=shortcut)
        self._listener: Any | None = None

    @property
    def name(self) -> str:
        return "pynput GlobalHotKeys (X11)"

    def is_available(self) -> bool:
        """Check if pynput package and X11 display are available."""
        # pynput global hotkeys require an X11 display (or Xwayland with DISPLAY)
        if not os.environ.get("DISPLAY"):
            logger.debug("pynput backend unavailable: DISPLAY environment variable is not set")
            return False

        try:
            from pynput import keyboard  # noqa: F401

            return True
        except Exception as e:
            logger.debug(f"pynput backend unavailable: {e}")
            return False

    def _convert_shortcut_format(self) -> str:
        """Convert shortcut notation to pynput hotkey syntax (e.g. <cmd>+.)."""
        if self.shortcut in ("Meta+.", "Super+."):
            return "<cmd>+."
        return self.shortcut

    def start(self, on_activate: Callable[[], None]) -> bool:
        """Start listening for hotkey using pynput."""
        if not self.is_available():
            logger.error("pynput backend is not available in current environment.")
            return False

        self.on_activate = on_activate
        hotkey_str = self._convert_shortcut_format()

        try:
            from pynput import keyboard

            self._listener = keyboard.GlobalHotKeys({hotkey_str: self._on_pynput_triggered})
            self._listener.start()
            self._is_running = True
            logger.info(f"pynput shortcut listener started for '{hotkey_str}'")
            return True
        except Exception as e:
            logger.error(f"Failed to start pynput shortcut listener: {e}", exc_info=True)
            self.stop()
            return False

    def _on_pynput_triggered(self) -> None:
        """Callback when pynput hotkey combination is pressed."""
        logger.info(f"pynput hotkey activated: {self.shortcut}")
        if self.on_activate:
            self.on_activate()

    def stop(self) -> None:
        """Stop pynput keyboard listener."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception as e:
                logger.debug(f"Error stopping pynput listener: {e}")
            self._listener = None

        self._is_running = False
        logger.info("pynput shortcut listener stopped.")
