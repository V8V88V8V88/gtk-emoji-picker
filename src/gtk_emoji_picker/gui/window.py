"""GTK4 Application Window for Emoji Picker."""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gtk  # noqa: E402

from gtk_emoji_picker.gui.category_bar import CategoryBar  # noqa: E402
from gtk_emoji_picker.gui.css import apply_css  # noqa: E402
from gtk_emoji_picker.gui.grid_view import EmojiGridView  # noqa: E402


class EmojiPickerWindow(Gtk.ApplicationWindow):  # type: ignore[misc]
    """Main GTK4 window housing search, category navigation bar, and emoji grid."""

    def __init__(
        self,
        application: Gtk.Application,
        title: str = "Emoji Picker",
        default_width: int = 440,
        default_height: int = 540,
        on_emoji_copy: Callable[[str], None] | None = None,
        on_close: Callable[[Gtk.Window], bool] | None = None,
    ) -> None:
        super().__init__(application=application)
        self.set_title(title)
        self.set_default_size(default_width, default_height)
        self.add_css_class("emoji-picker-window")

        apply_css()

        self._on_emoji_copy = on_emoji_copy
        self._on_close = on_close

        if self._on_close:
            self.connect("close-request", self._on_close)

        # Root box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_child(self.main_box)

        # Search Entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.add_css_class("emoji-search-entry")
        self.search_entry.set_placeholder_text("Search emojis...")
        self.main_box.append(self.search_entry)

        # Category Bar
        self.category_bar = CategoryBar(on_category_changed=self._on_category_filter_changed)
        self.main_box.append(self.category_bar)

        # Scrolled container for grid
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.add_css_class("emoji-scrolled-window")
        self.scrolled_window.set_vexpand(True)
        self.scrolled_window.set_hexpand(True)
        self.main_box.append(self.scrolled_window)

        # Grid view
        self.grid_view = EmojiGridView(on_emoji_activated=self._on_grid_emoji_activated)
        self.scrolled_window.set_child(self.grid_view)

        # Alias for backward compatibility
        self.emoji_list = self.grid_view

        # Key controller for shortcuts (e.g. Escape to close)
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    def _on_category_filter_changed(self, category: str | None) -> None:
        """Emitted when category tab changes."""
        if hasattr(self, "_on_search_query_changed") and callable(self._on_search_query_changed):
            self._on_search_query_changed(self.search_entry.get_text(), category)

    def _on_grid_emoji_activated(self, emoji_str: str) -> None:
        """Emitted when an emoji in the grid is selected/activated."""
        if self._on_emoji_copy:
            self._on_emoji_copy(emoji_str)

    def _on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        """Handle window keyboard shortcuts."""
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def focus_search(self) -> None:
        """Focus the search entry widget."""
        self.search_entry.grab_focus()

    def set_categories(self, categories: list[str]) -> None:
        """Update category filters to match the loaded emoji dataset."""
        self.category_bar.build_categories(categories)
