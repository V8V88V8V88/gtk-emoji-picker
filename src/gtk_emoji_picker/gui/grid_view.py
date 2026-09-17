"""Categorized emoji grid widgets for the GTK4 emoji picker."""

from collections import OrderedDict
from collections.abc import Callable, Sequence
from typing import Any

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from gtk_emoji_picker.domain.models import Emoji  # noqa: E402


class EmojiGridView(Gtk.Box):  # type: ignore[misc]
    """Vertical list of category sections composed of responsive FlowBox grids."""

    DEFAULT_CATEGORY = "Smileys & Emotion"

    def __init__(
        self,
        on_emoji_activated: Callable[[str], None] | None = None,
        max_children_per_line: int = 9,
        min_children_per_line: int = 4,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.add_css_class("emoji-grid-view")
        self.set_margin_top(10)
        self.set_margin_bottom(10)
        self.set_margin_start(10)
        self.set_margin_end(10)

        self._on_emoji_activated = on_emoji_activated
        self._max_children_per_line = max_children_per_line
        self._min_children_per_line = min_children_per_line
        self._emojis_data: list[dict[str, str]] = []
        self._flat_children: list[Gtk.FlowBoxChild] = []
        self._section_flowboxes: list[Gtk.FlowBox] = []

        self._empty_state = Gtk.Label(label="No emojis match this filter.")
        self._empty_state.add_css_class("emoji-empty-state")
        self._empty_state.set_halign(Gtk.Align.CENTER)
        self._empty_state.set_justify(Gtk.Justification.CENTER)
        self.append(self._empty_state)

    def populate(
        self,
        emojis: Sequence[Emoji | dict[str, Any]],
        on_activate: Callable[[str], None] | None = None,
        flat: bool = False,
    ) -> None:
        """Populate the grid.

        In ``flat`` (search-results) mode all matches are rendered inside a single
        FlowBox so arrow-key navigation flows seamlessly across categories; otherwise
        results are grouped into categorized sections.
        """
        if on_activate is not None:
            self._on_emoji_activated = on_activate

        normalized = self._normalize_emojis(emojis)
        self.clear()
        self._emojis_data = normalized

        if not normalized:
            self._empty_state.set_visible(True)
            return

        self._empty_state.set_visible(False)

        if flat:
            flowbox = self._build_flowbox()
            self._section_flowboxes.append(flowbox)

            for item in normalized:
                child = self._build_emoji_child(item)
                flowbox.insert(child, -1)
                self._flat_children.append(child)

            self.append(flowbox)
            return

        grouped = self._group_by_category(normalized)

        for category, items in grouped.items():
            section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            section.add_css_class("emoji-category-section")

            title = Gtk.Label(label=category)
            title.add_css_class("emoji-category-title")
            title.set_halign(Gtk.Align.START)
            section.append(title)

            flowbox = self._build_flowbox()
            self._section_flowboxes.append(flowbox)

            for item in items:
                child = self._build_emoji_child(item)
                flowbox.insert(child, -1)
                self._flat_children.append(child)

            section.append(flowbox)
            self.append(section)

    def clear(self) -> None:
        """Remove all rendered category sections and reset tracking."""
        self._flat_children.clear()
        self._section_flowboxes.clear()

        child = self.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            if child is not self._empty_state:
                self.remove(child)
            child = next_child

        self._empty_state.set_visible(False)

    def get_child_at_index(self, index: int) -> Gtk.FlowBoxChild | None:
        """Return a flattened child by index across all sections."""
        if 0 <= index < len(self._flat_children):
            return self._flat_children[index]
        return None

    def select_child(self, child: Gtk.FlowBoxChild) -> None:
        """Select a child inside its parent FlowBox."""
        parent = child.get_parent()
        if isinstance(parent, Gtk.FlowBox):
            parent.select_child(child)

    def get_selected_row(self) -> Gtk.FlowBoxChild | None:
        """Return the first selected child from any visible category section."""
        for flowbox in self._section_flowboxes:
            selected = flowbox.get_selected_children()
            if selected:
                return selected[0]
        return None

    def focus_first_child(self) -> bool:
        """Move keyboard focus to the first emoji child, returning True if one exists."""
        if not self._flat_children:
            return False
        first = self._flat_children[0]
        self.select_child(first)
        first.grab_focus()
        return True

    @property
    def emojis_data(self) -> list[dict[str, str]]:
        """Return the current flattened dataset shown in the grid."""
        return list(self._emojis_data)

    def _build_flowbox(self) -> Gtk.FlowBox:
        flowbox = Gtk.FlowBox()
        flowbox.add_css_class("emoji-grid")
        flowbox.set_valign(Gtk.Align.START)
        flowbox.set_halign(Gtk.Align.FILL)
        flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        flowbox.set_max_children_per_line(self._max_children_per_line)
        flowbox.set_min_children_per_line(self._min_children_per_line)
        flowbox.set_homogeneous(True)
        flowbox.set_row_spacing(6)
        flowbox.set_column_spacing(6)
        flowbox.connect("child-activated", self._on_child_activated)
        return flowbox

    def _build_emoji_child(self, item: dict[str, str]) -> Gtk.FlowBoxChild:
        glyph = item["emoji"]
        name = item.get("name", "")

        button = Gtk.Button(label=glyph)
        button.add_css_class("emoji-cell")
        button.set_can_focus(True)
        button.set_tooltip_text(name)
        button.connect("clicked", self._on_button_clicked, glyph)

        child = Gtk.FlowBoxChild()
        child.add_css_class("emoji-item")
        child.set_tooltip_text(name)
        child.set_child(button)
        child.set_focusable(True)
        return child

    def _on_button_clicked(self, button: Gtk.Button, emoji_str: str) -> None:
        if self._on_emoji_activated:
            self._on_emoji_activated(emoji_str)

    def _on_child_activated(self, flowbox: Gtk.FlowBox, child: Gtk.FlowBoxChild) -> None:
        button = child.get_child()
        if isinstance(button, Gtk.Button):
            label = button.get_label()
            if label and self._on_emoji_activated:
                self._on_emoji_activated(label)

    def _normalize_emojis(
        self,
        emojis: Sequence[Emoji | dict[str, Any]],
    ) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for item in emojis:
            if isinstance(item, Emoji):
                normalized.append(
                    {
                        "emoji": item.glyph,
                        "name": item.name,
                        "category": item.category or self.DEFAULT_CATEGORY,
                    }
                )
                continue

            if not isinstance(item, dict):
                continue

            glyph = str(item.get("emoji") or item.get("glyph") or "").strip()
            name = str(item.get("name") or "").strip()
            category = str(item.get("category") or self.DEFAULT_CATEGORY).strip()
            if glyph:
                normalized.append(
                    {
                        "emoji": glyph,
                        "name": name,
                        "category": category or self.DEFAULT_CATEGORY,
                    }
                )

        return normalized

    def _group_by_category(
        self,
        emojis: Sequence[dict[str, str]],
    ) -> "OrderedDict[str, list[dict[str, str]]]":
        grouped: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        for item in emojis:
            category = item.get("category") or self.DEFAULT_CATEGORY
            grouped.setdefault(category, []).append(item)
        return grouped
