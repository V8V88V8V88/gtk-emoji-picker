"""Shortcut listener backends package module."""

import os

from gtk_emoji_picker.infrastructure.shortcut_backends.base import BaseShortcutListener
from gtk_emoji_picker.infrastructure.shortcut_backends.keybinder import KeybinderShortcutListener
from gtk_emoji_picker.infrastructure.shortcut_backends.portal import PortalShortcutListener
from gtk_emoji_picker.infrastructure.shortcut_backends.pynput_backend import (
    PynputShortcutListener,
)

__all__ = [
    "BaseShortcutListener",
    "PortalShortcutListener",
    "KeybinderShortcutListener",
    "PynputShortcutListener",
    "get_backend_candidates",
    "select_best_backend",
]


def get_backend_candidates() -> list[type[BaseShortcutListener]]:
    """Return ordered list of backend candidate classes based on session environment."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

    if session_type == "wayland":
        return [
            PortalShortcutListener,
            PynputShortcutListener,
            KeybinderShortcutListener,
        ]
    else:
        # X11 or standard/unspecified desktop session
        return [
            KeybinderShortcutListener,
            PortalShortcutListener,
            PynputShortcutListener,
        ]


def select_best_backend(shortcut: str = "Meta+.") -> BaseShortcutListener | None:
    """Instantiate and return the first available shortcut listener backend for current env."""
    for backend_cls in get_backend_candidates():
        backend = backend_cls(shortcut=shortcut)
        if backend.is_available():
            return backend

    # Fallback to PortalShortcutListener as it handles D-Bus session gracefully
    return PortalShortcutListener(shortcut=shortcut)
