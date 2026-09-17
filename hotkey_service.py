#!/usr/bin/env python3
"""Global hotkey service entry point."""

import logging
import os
import signal
import subprocess
import sys

from gtk_emoji_picker.infrastructure.shortcut_daemon import ShortcutDaemon

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class HotkeyListener:
    """Service wrapper for global shortcut keybinding listening."""

    def __init__(self, shortcut: str = "Meta+.", picker_app=None):
        self.shortcut = shortcut
        self.picker_app = picker_app
        self.daemon: ShortcutDaemon | None = None
        self.listener = None  # Backward compatibility field

    def start(self) -> None:
        """Start listening for global hotkey."""
        try:
            self.daemon = ShortcutDaemon(
                shortcut=self.shortcut,
                on_trigger=self.on_shortcut_activated,
            )
            started = self.daemon.start()
            if started:
                self.listener = self.daemon.active_backend
                logging.info(f"Global hotkey listener started ({self.shortcut})")
            else:
                self._fallback_pynput()
        except Exception as e:
            logging.error(
                f"Failed to start global hotkey listener: {e}\n"
                "Note: Global hotkeys require a supported X11 or Wayland environment. "
                "If running Wayland, ensure XDG Desktop Portal is running or set up "
                "a system shortcut executing run-emoji-picker.sh.",
                exc_info=True,
            )
            sys.exit(1)

    def _fallback_pynput(self) -> None:
        try:
            from pynput import keyboard

            self.listener = keyboard.GlobalHotKeys(
                {
                    "<cmd>+.": self.on_shortcut_activated,
                }
            )
            self.listener.start()
            logging.info("Global hotkey listener started using pynput fallback (Meta + .)")
        except Exception as e:
            logging.error(f"Failed pynput fallback listener: {e}")
            sys.exit(1)

    def on_shortcut_activated(self) -> None:
        """Callback triggered when shortcut is pressed."""
        logging.info("Shortcut activated!")
        self.launch_emoji_picker()

    def launch_emoji_picker(self) -> None:
        """Launch emoji picker process."""
        try:
            if self.picker_app is not None:
                from gi.repository import GLib

                GLib.idle_add(self.picker_app.toggle_window)
                return

            script_dir = os.path.dirname(os.path.abspath(__file__))
            emoji_picker_path = os.path.join(script_dir, "emoji_picker.py")
            if not os.path.isfile(emoji_picker_path):
                logging.error(f"Emoji picker not found at: {emoji_picker_path}")
                return

            if not os.access(emoji_picker_path, os.X_OK):
                logging.info("Setting executable permission on emoji picker")
                os.chmod(emoji_picker_path, 0o755)

            command = os.environ.get(
                "GTK_EMOJI_PICKER_COMMAND", f"{sys.executable} -m gtk_emoji_picker"
            )
            command_parts = command.split()
            if "--toggle" not in command_parts:
                command_parts.append("--toggle")
            logging.info("Toggling emoji picker with command: %s", " ".join(command_parts))
            subprocess.Popen(command_parts)
        except Exception as e:
            logging.error(f"Failed to launch emoji picker: {e}", exc_info=True)

    def stop(self) -> None:
        """Stop shortcut listener."""
        if self.daemon:
            self.daemon.stop()
            self.daemon = None
        elif self.listener and hasattr(self.listener, "stop"):
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None


def main() -> int:
    """Main entry point for hotkey service daemon."""
    app = HotkeyListener()

    def signal_handler(signum, frame):
        logging.info("Received signal to terminate")
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    app.start()

    try:
        if app.daemon:
            app.daemon.run()
        elif app.listener and hasattr(app.listener, "join"):
            app.listener.join()
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt to terminate")
        app.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
