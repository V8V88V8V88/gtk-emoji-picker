"""Base interface for global shortcut listener backends."""

from abc import ABC, abstractmethod
from collections.abc import Callable


class BaseShortcutListener(ABC):
    """Abstract base class for global shortcut listener backends."""

    def __init__(self, shortcut: str = "Meta+.") -> None:
        self.shortcut = shortcut
        self.on_activate: Callable[[], None] | None = None
        self._is_running: bool = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Human readable backend identifier."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend dependencies and environment are available."""
        pass

    @abstractmethod
    def start(self, on_activate: Callable[[], None]) -> bool:
        """Start listening for the global shortcut.

        Returns True if listener started successfully.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop listening for global shortcuts."""
        pass

    @property
    def is_running(self) -> bool:
        """Return whether listener is currently active."""
        return self._is_running
