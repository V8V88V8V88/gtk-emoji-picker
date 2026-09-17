"""Emoji data provider implementations."""

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from gtk_emoji_picker.domain.models import Emoji

logger = logging.getLogger(__name__)


class BaseEmojiProvider(ABC):
    """Abstract base provider for loading domain Emoji objects."""

    @abstractmethod
    def load_emojis(self) -> Sequence[Emoji]:
        """Load and return emojis."""
        pass


class JsonEmojiProvider(BaseEmojiProvider):
    """Loads emoji data from a JSON file."""

    DEFAULT_CATEGORY = "Smileys & Emotion"

    FALLBACK_EMOJIS = (
        Emoji(
            "😊",
            "smiling face with smiling eyes",
            "Smileys & Emotion",
            ("happy", "smile", "blush"),
            "1.0",
        ),
        Emoji("👍", "thumbs up", "People & Body", ("like", "approve", "yes", "hand"), "1.0"),
        Emoji("❤️", "red heart", "Symbols", ("love", "heart", "like"), "1.0"),
    )

    def __init__(self, json_path: str | Path | None = None) -> None:
        if json_path is None:
            # Default to emojis.json in project root
            root_dir = Path(__file__).resolve().parents[3]
            json_path = root_dir / "emojis.json"
        self.json_path = Path(json_path)

    def _parse_record(self, item: dict[str, Any]) -> Emoji | None:
        parsed = Emoji.from_dict(item, default_category=self.DEFAULT_CATEGORY)
        if parsed is None:
            logger.warning(f"Invalid emoji record rejected: {item}")
        return parsed

    def load_emojis(self) -> Sequence[Emoji]:
        validated: list[Emoji] = []
        if self.json_path.exists():
            try:
                with open(self.json_path, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            parsed = self._parse_record(item)
                            if parsed:
                                validated.append(parsed)
                        if validated:
                            logger.info(f"Loaded {len(validated)} emojis from {self.json_path}")
                            return validated
                        logger.error(
                            f"No valid emoji records found in {self.json_path}; using fallback."
                        )
                    else:
                        logger.error(
                            f"Emoji JSON data in {self.json_path} is not a list; using fallback."
                        )
            except Exception as e:
                logger.error(f"Failed to load emojis from {self.json_path}: {e}")
        else:
            logger.warning(f"Emoji file {self.json_path} does not exist; using fallback.")

        return self.FALLBACK_EMOJIS


class InMemoryEmojiProvider(BaseEmojiProvider):
    """Provides emojis from an in-memory sequence of Emoji models."""

    def __init__(self, emojis: Sequence[Emoji] | None = None) -> None:
        self._emojis: tuple[Emoji, ...] = tuple(emojis) if emojis else ()

    def load_emojis(self) -> Sequence[Emoji]:
        return self._emojis


class DictEmojiProvider(BaseEmojiProvider):
    """Provides emojis from raw dictionary records."""

    def __init__(
        self, records: Sequence[dict[str, Any]], default_category: str = "Smileys & Emotion"
    ) -> None:
        self._records = records
        self._default_category = default_category

    def load_emojis(self) -> Sequence[Emoji]:
        emojis: list[Emoji] = []
        for record in self._records:
            parsed = Emoji.from_dict(record, default_category=self._default_category)
            if parsed:
                emojis.append(parsed)
        return tuple(emojis)


__all__ = ["BaseEmojiProvider", "JsonEmojiProvider", "InMemoryEmojiProvider", "DictEmojiProvider"]
