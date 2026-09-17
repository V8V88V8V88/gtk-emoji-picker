"""Keybinder3 backend for X11 GTK desktop environments."""

import logging
from collections.abc import Callable
from typing import Any

from gtk_emoji_picker.infrastructure.shortcut_backends.base import BaseShortcutListener

logger = logging.getLogger(__name__)


class KeybinderShortcutListener(BaseShortcutListener):
    """Global shortcut listener implementation using libkeybinder (Keybinder 3.0)."""

    def __init__(self, shortcut: str = "Meta+.") -> None:
        super().__init__(shortcut=shortcut)
        self._keybinder_mod: Any | None = None
        self._bound_accel: str | None = None

    @property
    def name(self) -> str:
        return "Keybinder 3.0 (X11 GTK)"

    def is_available(self) -> bool:
        """Check if Keybinder 3.0 GObject Introspection module is installed."""
        try:
            import gi

            gi.require_version("Keybinder", "3.0")
            from gi.repository import Keybinder

            self._keybinder_mod = Keybinder
            return True
        except Exception as e:
            logger.debug(f"Keybinder backend unavailable: {e}")
            return False

    def _convert_shortcut_format(self) -> str:
        """Convert shortcut notation (e.g. Meta+.) to Keybinder accelerator format."""
        if self.shortcut == "Meta+." or self.shortcut == "Super+.":
            return "<Super>period"
        return self.shortcut

    def start(self, on_activate: Callable[[], None]) -> bool:
        """Initialize Keybinder and bind accelerator."""
        if not self.is_available():
            logger.error("Keybinder 3.0 module is not available.")
            return False

        self.on_activate = on_activate
        accel = self._convert_shortcut_format()

        try:
            if self._keybinder_mod:
                self._keybinder_mod.init()
                success = self._keybinder_mod.bind(accel, self._on_keybinder_triggered, None)
                if success:
                    self._bound_accel = accel
                    self._is_running = True
                    logger.info(f"Keybinder shortcut listener bound to '{accel}'")
                    return True
                else:
                    logger.error(f"Keybinder failed to bind shortcut '{accel}'")
                    return False
        except Exception as e:
            logger.error(f"Error starting KeybinderShortcutListener: {e}", exc_info=True)

        return False

    def _on_keybinder_triggered(self, keystring: str, user_data: Any) -> None:
        """Callback invoked when Keybinder accelerator is pressed."""
        logger.info(f"Keybinder shortcut activated: {keystring}")
        if self.on_activate:
            self.on_activate()

    def stop(self) -> None:
        """Unbind accelerator and stop Keybinder listener."""
        if self._keybinder_mod and self._bound_accel:
            try:
                self._keybinder_mod.unbind(self._bound_accel)
            except Exception as e:
                logger.debug(f"Error unbinding Keybinder shortcut: {e}")
            self._bound_accel = None

        self._is_running = False
        logger.info("Keybinder shortcut listener stopped.")
