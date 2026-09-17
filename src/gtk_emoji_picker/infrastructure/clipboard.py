"""Clipboard and auto-paste infrastructure services."""

import logging
import os
import subprocess
import time
from collections.abc import Callable

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

logger = logging.getLogger(__name__)


class ClipboardService:
    """GTK4 GdkClipboard manager with fallback mechanisms to set text into system clipboard.

    Supports X11 and Wayland environments.
    """

    def __init__(self, display: Gdk.Display | None = None) -> None:
        self._display = display

    def get_clipboard(self) -> Gdk.Clipboard | None:
        """Retrieve default Gdk.Clipboard."""
        display = self._display or Gdk.Display.get_default()
        if display:
            return display.get_clipboard()
        logger.warning("No default Gdk.Display available for clipboard access.")
        return None

    def copy_text(self, text: str) -> bool:
        """Copy specified text string to clipboard using GdkClipboard or command fallbacks.

        Fallbacks include wl-copy, xclip, and xsel.
        """
        clipboard = self.get_clipboard()
        if clipboard:
            try:
                clipboard.set(text)
                logger.info(f"Successfully copied text to Gdk.Clipboard: {text!r}")
                return True
            except Exception as e:
                logger.error(f"Error copying text to Gdk.Clipboard: {e}", exc_info=True)

        # Fallback for Wayland/X11 CLI tools if Gdk.Clipboard fails or display is unavailable
        if self._copy_with_wl_copy(text):
            return True
        if self._copy_with_xclip(text):
            return True
        if self._copy_with_xsel(text):
            return True

        logger.error("Failed to copy text using all clipboard mechanisms.")
        return False

    def _copy_with_wl_copy(self, text: str) -> bool:
        try:
            subprocess.run(
                ["wl-copy", text],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Copied text via wl-copy.")
            return True
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.debug(f"wl-copy fallback failed: {e}")
            return False

    def _copy_with_xclip(self, text: str) -> bool:
        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.communicate(input=text.encode("utf-8"))
            if proc.returncode == 0:
                logger.info("Copied text via xclip.")
                return True
            return False
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.debug(f"xclip fallback failed: {e}")
            return False

    def _copy_with_xsel(self, text: str) -> bool:
        try:
            proc = subprocess.Popen(
                ["xsel", "--clipboard", "--input"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.communicate(input=text.encode("utf-8"))
            if proc.returncode == 0:
                logger.info("Copied text via xsel.")
                return True
            return False
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.debug(f"xsel fallback failed: {e}")
            return False


class AutoPasteService:
    """Service to simulate paste operation or character injection into active window.

    Supports X11 and Wayland.
    """

    def __init__(
        self,
        delay_seconds: float = 0.1,
        paste_executor: Callable[[], bool] | None = None,
    ) -> None:
        self.delay_seconds = delay_seconds
        self._paste_executor = paste_executor

    def paste(self) -> bool:
        """Simulate paste action into active window using abstracted backend mechanisms."""
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

        if self._paste_executor:
            return self._paste_executor()

        return self._default_paste()

    def _default_paste(self) -> bool:
        """Execute paste simulation via ydotool, wtype, xdotool, or pynput."""
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

        # On Wayland environments: try ydotool, wtype, pynput, xdotool
        if session_type == "wayland":
            if self._paste_with_ydotool():
                return True
            if self._paste_with_wtype():
                return True
            if self._paste_with_pynput():
                return True
            if self._paste_with_xdotool():
                return True
        else:
            # On X11 / standard environments: try xdotool, ydotool, pynput, wtype
            if self._paste_with_xdotool():
                return True
            if self._paste_with_ydotool():
                return True
            if self._paste_with_pynput():
                return True
            if self._paste_with_wtype():
                return True

        logger.warning(
            "Auto-paste simulation failed: No compatible input injection backend succeeded."
        )
        return False

    def _paste_with_ydotool(self) -> bool:
        """Simulate Ctrl+V paste via ydotool (works on Wayland & X11)."""
        try:
            # ydotool key 29:1 47:1 47:0 29:0 (Ctrl down, V down, V up, Ctrl up)
            subprocess.run(
                ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Auto-pasted clipboard content via ydotool (Ctrl+v).")
            return True
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.debug(f"ydotool paste unavailable or failed: {e}")
            return False

    def _paste_with_wtype(self) -> bool:
        """Simulate Ctrl+V paste via wtype (Wayland / wlroots)."""
        try:
            subprocess.run(
                ["wtype", "-M", "ctrl", "v"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Auto-pasted clipboard content via wtype (Ctrl+v).")
            return True
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.debug(f"wtype paste unavailable or failed: {e}")
            return False

    def _paste_with_xdotool(self) -> bool:
        """Simulate Ctrl+V paste via xdotool (X11 / Xwayland)."""
        try:
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Auto-pasted clipboard content via xdotool (ctrl+v).")
            return True
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.debug(f"xdotool paste unavailable or failed: {e}")
            return False

    def _paste_with_pynput(self) -> bool:
        """Simulate Ctrl+V paste via pynput."""
        try:
            from pynput.keyboard import Controller, Key

            keyboard = Controller()
            with keyboard.pressed(Key.ctrl):
                keyboard.press("v")
                keyboard.release("v")
            logger.info("Auto-pasted clipboard content via pynput (Ctrl+v).")
            return True
        except Exception as e:
            logger.debug(f"pynput paste failed: {e}")
            return False
