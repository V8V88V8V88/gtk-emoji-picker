"""Shortcut daemon infrastructure service for global hotkey handling."""

import logging
import shutil
import signal
import subprocess
import sys
from collections.abc import Callable

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

from gtk_emoji_picker.infrastructure.shortcut_backends import (
    BaseShortcutListener,
    get_backend_candidates,
    select_best_backend,
)

logger = logging.getLogger(__name__)


class ShortcutDaemon:
    """Daemon service that listens for a global shortcut and triggers an action."""

    TOGGLE_ARGUMENT = "--toggle"

    def __init__(
        self,
        shortcut: str = "Meta+.",
        on_trigger: Callable[[], None] | None = None,
    ) -> None:
        self.shortcut = shortcut
        self.on_trigger = on_trigger or self.toggle_emoji_picker
        self.active_backend: BaseShortcutListener | None = None
        self._main_loop: GLib.MainLoop | None = None
        self._is_running = False

    def launch_emoji_picker(self) -> None:
        """Launch the emoji picker process."""
        try:
            picker_exec = shutil.which("gtk-emoji-picker")
            if picker_exec:
                command = [picker_exec]
            else:
                command = [sys.executable, "-m", "gtk_emoji_picker"]

            logger.info("Launching emoji picker: %s", " ".join(command))
            subprocess.Popen(command)
        except Exception as exc:
            logger.error("Failed to launch emoji picker process: %s", exc, exc_info=True)

    def toggle_emoji_picker(self) -> None:
        """Toggle the single-instance emoji picker window via ``--toggle``.

        The spawned process is a Gtk.Application client: if the picker is already
        running it is forwarded to the primary instance over D-Bus, otherwise it
        becomes the primary instance and shows the window.
        """
        try:
            picker_exec = shutil.which("gtk-emoji-picker")
            if picker_exec:
                command = [picker_exec, self.TOGGLE_ARGUMENT]
            else:
                command = [sys.executable, "-m", "gtk_emoji_picker", self.TOGGLE_ARGUMENT]

            logger.info("Toggling emoji picker: %s", " ".join(command))
            subprocess.Popen(command)
        except Exception as exc:
            logger.error("Failed to toggle emoji picker process: %s", exc, exc_info=True)

    def start(self) -> bool:
        """Select backend and start shortcut listener daemon."""
        candidates = get_backend_candidates()

        for backend_cls in candidates:
            backend = backend_cls(shortcut=self.shortcut)
            if backend.is_available():
                logger.info(f"Attempting to start shortcut backend: {backend.name}")
                if backend.start(self.on_trigger):
                    self.active_backend = backend
                    self._is_running = True
                    logger.info(
                        f"Shortcut daemon active with backend '{backend.name}' "
                        f"on shortcut '{self.shortcut}'"
                    )
                    return True

        # Fallback selection attempt
        fallback_backend = select_best_backend(shortcut=self.shortcut)
        if fallback_backend and fallback_backend.start(self.on_trigger):
            self.active_backend = fallback_backend
            self._is_running = True
            logger.info(f"Shortcut daemon active with fallback backend '{fallback_backend.name}'")
            return True

        logger.error("No shortcut listener backend could be started successfully.")
        return False

    def run(self) -> int:
        """Start daemon and enter main loop until stopped."""
        if not self.is_running and not self.start():
            return 1

        self._main_loop = GLib.MainLoop()

        def _sig_handler(signum: int, frame: object) -> None:
            logger.info(f"Received signal {signum}, stopping daemon...")
            self.stop()
            if self._main_loop and self._main_loop.is_running():
                self._main_loop.quit()

        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)

        try:
            self._main_loop.run()
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received, exiting...")
            self.stop()

        return 0

    def stop(self) -> None:
        """Stop shortcut listener backend and main loop."""
        if self.active_backend:
            self.active_backend.stop()
            self.active_backend = None

        if self._main_loop and self._main_loop.is_running():
            self._main_loop.quit()

        self._is_running = False
        logger.info("Shortcut daemon stopped.")

    @property
    def is_running(self) -> bool:
        """Return True if shortcut daemon is currently active."""
        return self._is_running


def main() -> int:
    """CLI entry point for shortcut daemon process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    daemon = ShortcutDaemon(shortcut="Meta+.")
    return daemon.run()


if __name__ == "__main__":
    sys.exit(main())
