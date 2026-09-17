import os
from abc import ABC, abstractmethod
from typing import Any

from gtk_emoji_picker.infrastructure.emoji_provider import JsonEmojiProvider
from gtk_emoji_picker.services.emoji_search_engine import EmojiSearchEngine


class EmojiRepository(ABC):
    @abstractmethod
    def list_emojis(self) -> list[dict[str, str]]:
        """Return all emojis in the repository."""
        pass

    @abstractmethod
    def search_emojis(self, query: str) -> list[dict[str, str]]:
        """Search emojis by matching query against name."""
        pass


class JsonEmojiRepository(EmojiRepository):
    FALLBACK_EMOJIS = [
        {"emoji": "😊", "name": "smiling face"},
        {"emoji": "👍", "name": "thumbs up"},
        {"emoji": "❤️", "name": "heart"},
    ]

    def __init__(self, json_filepath: str = None):
        if json_filepath is None:
            json_filepath = os.path.join(os.path.dirname(__file__), "emojis.json")
        self.json_filepath = json_filepath
        self._provider = JsonEmojiProvider(self.json_filepath)
        self._search_engine = EmojiSearchEngine(provider=self._provider)

    def _validate_record(self, item: dict) -> dict[str, str] | None:
        parsed = self._provider._parse_record(item)
        if parsed is None:
            return None
        return {
            "emoji": parsed.glyph,
            "name": parsed.name,
            "category": parsed.category or "Smileys & Emotion",
        }

    def list_emojis(self, category: str | None = None) -> list[dict[str, Any]]:
        emojis = self._search_engine.search(query="", category=category)
        res = []
        for e in emojis:
            item: dict[str, Any] = {
                "emoji": e.glyph,
                "name": e.name,
                "category": e.category or "Smileys & Emotion",
            }
            if e.keywords:
                item["keywords"] = list(e.keywords)
            if e.skin_tone_variants:
                item["skin_tone_variants"] = list(e.skin_tone_variants)
            if e.annotations:
                item["annotations"] = list(e.annotations)
            if e.shortcodes:
                item["shortcodes"] = list(e.shortcodes)
            res.append(item)
        return res

    def get_categories(self) -> list[str]:
        return list(self._search_engine.get_categories())

    def search_emojis(self, query: str = None, category: str | None = None) -> list[dict[str, Any]]:
        if query is not None and not isinstance(query, str):
            raise TypeError(f"Query must be a string or None, got {type(query).__name__}")

        emojis = self._search_engine.search(query=query or "", category=category)
        res = []
        for e in emojis:
            item: dict[str, Any] = {
                "emoji": e.glyph,
                "name": e.name,
                "category": e.category or "Smileys & Emotion",
            }
            if e.keywords:
                item["keywords"] = list(e.keywords)
            if e.skin_tone_variants:
                item["skin_tone_variants"] = list(e.skin_tone_variants)
            if e.annotations:
                item["annotations"] = list(e.annotations)
            if e.shortcodes:
                item["shortcodes"] = list(e.shortcodes)
            res.append(item)
        return res
