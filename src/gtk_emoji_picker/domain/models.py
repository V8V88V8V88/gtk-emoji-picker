from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class Emoji:
    """Domain model representing a single emoji item."""

    glyph: str
    name: str
    category: str = "Smileys & Emotion"
    keywords: tuple[str, ...] = field(default_factory=tuple)
    unicode_version: str = "1.0"
    skin_tone_variants: tuple[str, ...] = field(default_factory=tuple)
    annotations: tuple[str, ...] = field(default_factory=tuple)
    shortcodes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert Emoji instance to dictionary representation."""
        return {
            "glyph": self.glyph,
            "name": self.name,
            "category": self.category,
            "keywords": list(self.keywords),
            "unicode_version": self.unicode_version,
            "skin_tone_variants": list(self.skin_tone_variants),
            "annotations": list(self.annotations),
            "shortcodes": list(self.shortcodes),
        }

    @classmethod
    def from_dict(
        cls, item: dict[str, Any], default_category: str = "Smileys & Emotion"
    ) -> "Emoji | None":
        """Construct Emoji instance from dictionary data, returning None if invalid."""
        if not isinstance(item, dict):
            return None

        glyph = item.get("emoji") or item.get("glyph") or item.get("character")
        name = item.get("name") or item.get("description") or item.get("label")

        if not isinstance(glyph, str) or not isinstance(name, str):
            return None

        glyph = glyph.strip()
        name = name.strip()

        if not glyph or not name:
            return None

        category = item.get("category", default_category)
        if not isinstance(category, str) or not category.strip():
            category = default_category
        else:
            category = category.strip()

        def _parse_str_sequence(raw: Any) -> tuple[str, ...]:
            if isinstance(raw, (list, tuple)):
                return tuple(
                    str(item).strip().lower()
                    for item in raw
                    if isinstance(item, str) and item.strip()
                )
            if isinstance(raw, str) and raw.strip():
                return tuple(item.strip().lower() for item in raw.split(",") if item.strip())
            return ()

        keywords = _parse_str_sequence(item.get("keywords"))
        annotations = _parse_str_sequence(item.get("annotations"))
        shortcodes = _parse_str_sequence(item.get("shortcodes"))

        raw_variants = item.get("skin_tone_variants") or item.get("variants")
        skin_tone_variants: tuple[str, ...] = ()
        if isinstance(raw_variants, (list, tuple)):
            skin_tone_variants = tuple(
                str(v).strip() for v in raw_variants if isinstance(v, str) and v.strip()
            )
        elif isinstance(raw_variants, dict):
            skin_tone_variants = tuple(
                str(v).strip() for v in raw_variants.values() if isinstance(v, str) and v.strip()
            )

        unicode_ver = str(item.get("unicode_version", "1.0")).strip() or "1.0"

        return cls(
            glyph=glyph,
            name=name,
            category=category,
            keywords=keywords,
            unicode_version=unicode_ver,
            skin_tone_variants=skin_tone_variants,
            annotations=annotations,
            shortcodes=shortcodes,
        )


class EmojiProvider(Protocol):
    """Protocol for providing/accessing emoji raw dataset or source."""

    def load_emojis(self) -> Sequence[Emoji]: ...


class EmojiRepository(Protocol):
    """Protocol for accessing emoji dataset storage."""

    def list_emojis(self, category: str | None = None) -> Sequence[Emoji]: ...

    def search_emojis(
        self, query: str | None = None, category: str | None = None
    ) -> Sequence[Emoji]: ...

    def get_categories(self) -> Sequence[str]: ...


class EmojiCatalog(Protocol):
    """Protocol for searching and querying emoji records."""

    def search(self, query: str = "", category: str | None = None) -> Sequence[Emoji]: ...

    def get_categories(self) -> Sequence[str]: ...


class ClipboardPort(Protocol):
    """Protocol for interacting with the system clipboard."""

    def copy_text(self, value: str) -> None: ...


class ShortcutBackend(Protocol):
    """Protocol for global hotkey listeners."""

    def start(self) -> None: ...

    def stop(self) -> None: ...
