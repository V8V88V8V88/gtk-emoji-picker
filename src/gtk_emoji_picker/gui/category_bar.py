"""Category selection bar widget for GTK4 Emoji Picker."""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

CATEGORY_MAP: dict[str, str] = {
    "All": "🌐 All",
    "Smileys & Emotion": "😀 Smileys",
    "People & Body": "🧑 People",
    "Animals & Nature": "🐶 Animals",
    "Food & Drink": "🍕 Food",
    "Travel & Places": "✈️ Travel",
    "Activities": "⚽ Activities",
    "Objects": "💡 Objects",
    "Symbols": "🔣 Symbols",
    "Flags": "🚩 Flags",
}


class CategoryBar(Gtk.ScrolledWindow):  # type: ignore[misc]
    """Horizontal scrollable category selection bar widget."""

    def __init__(
        self,
        categories: list[str] | None = None,
        on_category_changed: Callable[[str | None], None] | None = None,
    ) -> None:
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.add_css_class("category-bar-scrolled")

        self._on_category_changed = on_category_changed
        self._active_category: str | None = None
        self._buttons: dict[str | None, Gtk.Button] = {}

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.box.add_css_class("category-bar-box")
        self.set_child(self.box)

        categories_list = categories if categories is not None else list(CATEGORY_MAP.keys())
        self.build_categories(categories_list)

    def build_categories(self, categories: list[str]) -> None:
        """Construct buttons for the given list of categories."""
        # Clear existing buttons
        while (child := self.box.get_first_child()) is not None:
            self.box.remove(child)
        self._buttons.clear()

        # Always include "All" option if not explicitly present
        all_categories = list(categories)
        if "All" not in all_categories:
            all_categories.insert(0, "All")

        for cat in all_categories:
            label_text = CATEGORY_MAP.get(cat, f"🏷️ {cat}")
            btn = Gtk.Button(label=label_text)
            btn.add_css_class("category-btn")

            category_val = None if cat == "All" else cat
            btn.connect("clicked", self._on_button_clicked, category_val)

            self.box.append(btn)
            self._buttons[category_val] = btn

        self.set_active_category(None)

    def _on_button_clicked(self, button: Gtk.Button, category: str | None) -> None:
        self.set_active_category(category)
        if self._on_category_changed:
            self._on_category_changed(category)

    def set_active_category(self, category: str | None) -> None:
        """Set active category and update visual active state of category buttons."""
        self._active_category = category
        for cat_key, btn in self._buttons.items():
            if cat_key == category:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

    @property
    def active_category(self) -> str | None:
        """Return currently active category filter."""
        return self._active_category
