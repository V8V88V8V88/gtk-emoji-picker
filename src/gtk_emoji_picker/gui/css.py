"""GTK4 CSS styling provider for visual focus states and responsive grid layout."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gtk  # noqa: E402

EMOJI_PICKER_STYLE_CSS = """
/* Emoji Picker Window and Main Container Styling */
.emoji-picker-window {
    background-color: @window_bg_color;
}

/* Category Selection Bar Styling */
.category-bar-box {
    padding: 6px 8px;
    border-bottom: 1px solid rgba(128, 128, 128, 0.2);
}

button.category-btn {
    border-radius: 16px;
    padding: 4px 10px;
    margin: 2px 3px;
    font-size: 13px;
    background-color: transparent;
    border: 1px solid transparent;
    transition: all 150ms ease-in-out;
}

button.category-btn:hover {
    background-color: rgba(128, 128, 128, 0.15);
}

button.category-btn.active {
    background-color: #3584e4;
    color: #ffffff;
    font-weight: bold;
}

/* Scrolled Container */
.emoji-scrolled-window {
    padding: 4px;
}

box.emoji-grid-view {
    background-color: transparent;
}

box.emoji-category-section {
    margin-bottom: 4px;
}

label.emoji-category-title {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.02em;
    opacity: 0.85;
    margin-left: 4px;
}

label.emoji-empty-state {
    margin-top: 48px;
    opacity: 0.72;
}

/* Emoji FlowBox Grid View */
flowbox.emoji-grid {
    padding: 2px;
    background-color: transparent;
}

flowboxchild.emoji-item {
    border-radius: 8px;
    padding: 0;
    margin: 2px;
    background-color: transparent;
    border: 2px solid transparent;
    transition: all 120ms ease-in-out;
}

flowboxchild.emoji-item:hover {
    background-color: rgba(53, 132, 228, 0.15);
    border-color: rgba(53, 132, 228, 0.3);
}

flowboxchild.emoji-item:focus,
flowboxchild.emoji-item:focus-within,
flowboxchild.emoji-item:selected {
    background-color: rgba(53, 132, 228, 0.3);
    border-color: #3584e4;
    outline: none;
}

button.emoji-cell {
    min-width: 44px;
    min-height: 44px;
    padding: 4px;
    border-radius: 8px;
    border: none;
    background: transparent;
}

button.emoji-cell:hover {
    background-color: rgba(53, 132, 228, 0.12);
}

button.emoji-cell:focus-visible {
    box-shadow: inset 0 0 0 2px #3584e4;
    background-color: rgba(53, 132, 228, 0.18);
}

button.emoji-cell > label {
    font-size: 26px;
}

/* Search Entry Styling */
.emoji-search-entry {
    margin: 8px 8px 4px 8px;
    border-radius: 10px;
}
"""


def apply_css() -> None:
    """Apply application CSS provider to current default display."""
    display = Gdk.Display.get_default()
    if display is None:
        return

    css_provider = Gtk.CssProvider()
    css_provider.load_from_string(EMOJI_PICKER_STYLE_CSS)
    Gtk.StyleContext.add_provider_for_display(
        display,
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
