#!/usr/bin/env python3
"""GTK4 emoji picker application entrypoint."""

import logging
import sys
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")

from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from emoji_repository import EmojiRepository, JsonEmojiRepository  # noqa: E402
from gtk_emoji_picker.gui import EmojiPickerWindow, apply_css  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class EmojiPicker(Gtk.Application):
    """GTK4 Emoji Picker Application.

    Uses a Gtk.Application D-Bus name to enforce a single running instance;
    subsequent launches are forwarded to the primary instance so the global
    shortcut daemon can request a window visibility toggle.
    """

    TOGGLE_ARGUMENT = "--toggle"

    def __init__(
        self,
        repository: EmojiRepository | None = None,
        is_daemon: bool = False,
        auto_paste: bool = True,
        clipboard_service: Any | None = None,
        auto_paste_service: Any | None = None,
        search_debounce_ms: int = 150,
    ) -> None:
        super().__init__(
            application_id="org.example.emojipicker",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.repository = repository if repository is not None else JsonEmojiRepository()
        self.is_daemon = is_daemon
        self.auto_paste = auto_paste
        self._clipboard_service = clipboard_service
        self._auto_paste_service = auto_paste_service
        self.window: EmojiPickerWindow | None = None
        self.search_entry: Gtk.SearchEntry | None = None
        self.category_bar: Any | None = None
        self.emoji_list: Any | None = None
        self.filtered_emojis: list[dict[str, str]] = []
        self.emojis: list[dict[str, str]] = []
        self.search_debounce_ms = max(search_debounce_ms, 0)
        self._search_timeout_id: int | None = None
        self._search_generation = 0
        self.load_emojis()

    def _get_clipboard_service(self) -> Any:
        if self._clipboard_service is None:
            from gtk_emoji_picker.infrastructure.clipboard import ClipboardService

            self._clipboard_service = ClipboardService()
        return self._clipboard_service

    def _get_auto_paste_service(self) -> Any:
        if self._auto_paste_service is None:
            from gtk_emoji_picker.infrastructure.clipboard import AutoPasteService

            self._auto_paste_service = AutoPasteService()
        return self._auto_paste_service

    def load_emojis(self) -> None:
        self.emojis = list(self.repository.list_emojis())

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        """Handle command line arguments from the shortcut daemon or shell.

        ``--toggle`` flips window visibility on the single instance; without it
        the picker is simply shown (default activation behavior).
        """
        args = command_line.get_arguments()
        if self.TOGGLE_ARGUMENT in args:
            self.toggle_window()
        else:
            self.activate()
        return 0

    def _on_close_request(self, window: Gtk.Window) -> bool:
        if self.is_daemon:
            window.set_visible(False)
            return True
        self.window = None
        return False

    def toggle_window(self) -> None:
        if self.window and self.window.get_visible():
            self.window.set_visible(False)
        elif self.window:
            self._reset_view()
            self.window.present()
            if self.search_entry:
                self.search_entry.grab_focus()
        else:
            self.activate()

    def _reset_view(self) -> None:
        """Clear search text/category and restore the default categorized grid."""
        if self.search_entry:
            self.search_entry.set_text("")
        if self.category_bar:
            self.category_bar.set_active_category(None)
        self.populate_emoji_list()

    def do_activate(self) -> None:
        if not self.window:
            apply_css()

            self.window = EmojiPickerWindow(
                application=self,
                title="Emoji Picker",
                default_width=440,
                default_height=540,
                on_emoji_copy=self.copy_emoji_and_close,
                on_close=self._on_close_request,
            )

            self.search_entry = self.window.search_entry
            self.category_bar = self.window.category_bar
            self.emoji_list = self.window.grid_view

            self.search_entry.connect("search-changed", self.on_search_changed)
            self.search_entry.connect("activate", self.on_search_activate)

            search_key_controller = Gtk.EventControllerKey.new()
            search_key_controller.connect("key-pressed", self._on_search_key_pressed)
            self.search_entry.add_controller(search_key_controller)

            if self.category_bar:
                self.category_bar._on_category_changed = self._on_category_changed

            self.window._on_search_query_changed = lambda query, cat: self.populate_emoji_list(
                query, cat
            )

            self.populate_emoji_list()
        else:
            self._reset_view()

        self.window.present()
        if self.search_entry:
            self.search_entry.grab_focus()

    def _on_category_changed(self, category: str | None) -> None:
        filter_text = self.search_entry.get_text() if self.search_entry else ""
        self.populate_emoji_list(filter_text=filter_text, category=category)

    def on_key_pressed(
        self,
        controller: Any,
        keyval: int,
        keycode: int,
        state: Any,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            if self.window:
                self.window.close()
            return True
        return False

    def populate_emoji_list(
        self,
        filter_text: str | None = None,
        category: str | None = None,
    ) -> None:
        if category is None and self.category_bar is not None:
            category = self.category_bar.active_category

        query = filter_text or ""
        is_search = bool(query.strip())

        try:
            self.filtered_emojis = self.repository.search_emojis(query=query, category=category)
        except TypeError:
            self.filtered_emojis = self.repository.search_emojis(query)

        if hasattr(self.emoji_list, "populate"):
            self.emoji_list.populate(
                self.filtered_emojis,
                on_activate=self.copy_emoji_and_close,
                flat=is_search,
            )
        elif self.emoji_list is not None:
            if hasattr(self.emoji_list, "remove_all"):
                self.emoji_list.remove_all()
            else:
                while (child := self.emoji_list.get_first_child()) is not None:
                    self.emoji_list.remove(child)

            for emoji in self.filtered_emojis:
                label = Gtk.Label(label=f"{emoji['emoji']} {emoji['name']}")
                if hasattr(label, "set_halign"):
                    label.set_halign(Gtk.Align.START)
                self.emoji_list.append(label)

        self._scroll_results_to_top()

    def _scroll_results_to_top(self) -> None:
        """Reset the scrolled window viewport to the top after repopulating."""
        if self.window is None:
            return
        scrolled = getattr(self.window, "scrolled_window", None)
        if scrolled is None:
            return
        adjustment = scrolled.get_vadjustment()
        if adjustment is not None:
            adjustment.set_value(adjustment.get_lower())

    def on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._schedule_search_filter()

    def _schedule_search_filter(self) -> None:
        """Schedule a debounced grid refresh after typing pauses."""
        self._cancel_pending_search()
        generation = self._search_generation
        self._search_timeout_id = GLib.timeout_add(
            self.search_debounce_ms,
            self._on_search_debounce_fired,
            generation,
        )

    def _cancel_pending_search(self) -> None:
        """Cancel any scheduled debounced search and bump the generation guard."""
        if self._search_timeout_id is not None:
            GLib.source_remove(self._search_timeout_id)
            self._search_timeout_id = None
        self._search_generation += 1

    def _on_search_debounce_fired(self, generation: int) -> bool:
        """Apply the latest search query once the debounce window elapses."""
        self._search_timeout_id = None
        if generation != self._search_generation:
            return GLib.SOURCE_REMOVE
        text = self.search_entry.get_text() if self.search_entry else ""
        self.populate_emoji_list(filter_text=text)
        return GLib.SOURCE_REMOVE

    def _on_search_key_pressed(
        self,
        controller: Any,
        keyval: int,
        keycode: int,
        state: Any,
    ) -> bool:
        """Move keyboard focus from the search entry into the emoji results grid."""
        if keyval in (Gdk.KEY_Down, Gdk.KEY_KP_Down):
            focus_first = getattr(self.emoji_list, "focus_first_child", None)
            if callable(focus_first) and focus_first():
                return True
        return False

    def on_search_activate(self, entry: Gtk.SearchEntry) -> None:
        selected_row = None
        if self.emoji_list and hasattr(self.emoji_list, "get_selected_row"):
            selected_row = self.emoji_list.get_selected_row()

        if selected_row:
            index = selected_row.get_index()
            if 0 <= index < len(self.filtered_emojis):
                self.copy_emoji_and_close(self.filtered_emojis[index]["emoji"])
                return

        if self.filtered_emojis:
            self.copy_emoji_and_close(self.filtered_emojis[0]["emoji"])

    def copy_emoji_and_close(self, emoji: str) -> None:
        try:
            cb_service = self._get_clipboard_service()
            copied = cb_service.copy_text(emoji)
            if copied:
                logging.info(f"Copied emoji to clipboard: {emoji}")
            else:
                logging.warning("Failed to copy emoji to clipboard via ClipboardService.")
        except Exception as e:
            logging.error(f"Failed to copy emoji to clipboard: {e}")
        finally:
            if self.window:
                if self.is_daemon:
                    self.window.set_visible(False)
                else:
                    self.window.close()

            if self.auto_paste:
                try:
                    ap_service = self._get_auto_paste_service()
                    ap_service.paste()
                except Exception as e:
                    logging.error(f"Failed auto-paste simulation: {e}")

    def on_emoji_selected(self, list_box: Any, row: Any) -> None:
        try:
            index = row.get_index()
            if 0 <= index < len(self.filtered_emojis):
                emoji = self.filtered_emojis[index]["emoji"]
                self.copy_emoji_and_close(emoji)
        except Exception as e:
            logging.error(f"Failed to select emoji: {e}")


def main() -> int:
    app = EmojiPicker()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
