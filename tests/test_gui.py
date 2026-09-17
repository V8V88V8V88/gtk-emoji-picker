"""Tests for GTK4 GUI components (EmojiPickerWindow, EmojiGridView, CategoryBar, CSS)."""

from unittest.mock import MagicMock

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gtk  # noqa: E402

from gtk_emoji_picker.gui.category_bar import CategoryBar  # noqa: E402
from gtk_emoji_picker.gui.css import apply_css  # noqa: E402
from gtk_emoji_picker.gui.grid_view import EmojiGridView  # noqa: E402
from gtk_emoji_picker.gui.window import EmojiPickerWindow  # noqa: E402


def test_apply_css_does_not_raise_exception() -> None:
    """Verify apply_css runs safely."""
    apply_css()


def test_category_bar_initialization_and_selection() -> None:
    """Test CategoryBar button construction, category switching, and callbacks."""
    changed_categories: list[str | None] = []

    def on_changed(cat: str | None) -> None:
        changed_categories.append(cat)

    cat_bar = CategoryBar(on_category_changed=on_changed)

    # Default active category is None ("All")
    assert cat_bar.active_category is None

    # Simulate clicking "Smileys & Emotion" button
    smileys_button = cat_bar._buttons.get("Smileys & Emotion")
    assert smileys_button is not None
    smileys_button.emit("clicked")

    assert cat_bar.active_category == "Smileys & Emotion"
    assert "Smileys & Emotion" in changed_categories

    # Click "All" button
    all_button = cat_bar._buttons.get(None)
    assert all_button is not None
    all_button.emit("clicked")

    assert cat_bar.active_category is None
    assert changed_categories[-1] is None


def test_emoji_grid_view_population_and_activation() -> None:
    """Test EmojiGridView population with Emoji objects and dicts, and activation handling."""
    activated_emojis: list[str] = []

    grid = EmojiGridView(on_emoji_activated=lambda e: activated_emojis.append(e))

    sample_emojis = [
        {"emoji": "🚀", "name": "rocket", "category": "Travel & Places"},
        {"emoji": "🎉", "name": "party popper", "category": "Activities"},
    ]

    grid.populate(sample_emojis)
    assert len(grid.emojis_data) == 2
    assert len(grid._section_flowboxes) == 2

    # Check child item creation
    first_child = grid.get_child_at_index(0)
    assert first_child is not None
    assert isinstance(first_child, Gtk.FlowBoxChild)
    assert first_child.get_tooltip_text() == "rocket"

    # Test selection and get_selected_row helper
    grid.select_child(first_child)
    selected = grid.get_selected_row()
    assert selected == first_child
    assert selected.get_index() == 0

    # Emit child-activated signal on inner flowbox
    grid._section_flowboxes[0].emit("child-activated", first_child)
    assert activated_emojis == ["🚀"]

    # Test clearing grid
    grid.clear()
    assert grid.get_child_at_index(0) is None


def test_emoji_grid_view_flat_search_mode_and_focus_entry() -> None:
    """Test flat search-results rendering and keyboard focus entry into the grid."""
    grid = EmojiGridView()
    sample = [
        {"emoji": "🚀", "name": "rocket", "category": "Travel & Places"},
        {"emoji": "❤️", "name": "red heart", "category": "Symbols"},
    ]

    # Flat mode renders all matches in a single FlowBox for seamless navigation
    grid.populate(sample, flat=True)
    assert len(grid._section_flowboxes) == 1
    assert len(grid._flat_children) == 2
    assert len(grid.emojis_data) == 2
    assert grid.get_child_at_index(0) is not None
    assert grid.get_child_at_index(1) is not None

    # Keyboard focus can move from the search box into the first result
    assert grid.focus_first_child() is True
    assert grid.get_selected_row() == grid.get_child_at_index(0)

    # Clearing restores the grouped-by-category (default) layout
    grid.clear()
    assert grid.get_child_at_index(0) is None
    assert grid.focus_first_child() is False

    grid.populate(sample, flat=False)
    assert len(grid._section_flowboxes) == 2
    assert grid.focus_first_child() is True


def test_emoji_picker_window_construction_and_interactions() -> None:
    """Test EmojiPickerWindow layout, key controller, and category filter integration."""
    app = Gtk.Application(application_id="org.example.testgui")

    copied_emojis: list[str] = []

    window = EmojiPickerWindow(
        application=app,
        title="Test Emoji Window",
        on_emoji_copy=lambda e: copied_emojis.append(e),
    )

    assert window.get_title() == "Test Emoji Window"
    assert isinstance(window.search_entry, Gtk.SearchEntry)
    assert isinstance(window.category_bar, CategoryBar)
    assert isinstance(window.grid_view, EmojiGridView)
    window.set_categories(["Smileys & Emotion", "Objects"])
    assert "Objects" in window.category_bar._buttons

    # Focus search test
    window.focus_search()

    # Escape key pressed event
    mock_controller = MagicMock()
    handled = window._on_key_pressed(mock_controller, Gdk.KEY_Escape, 0, 0)
    assert handled is True

    other_key_handled = window._on_key_pressed(mock_controller, Gdk.KEY_a, 0, 0)
    assert other_key_handled is False
