from collections.abc import Sequence

from gtk_emoji_picker.domain.models import Emoji, EmojiCatalog, EmojiRepository
from gtk_emoji_picker.services.emoji_search_engine import EmojiSearchEngine


class DomainEmojiCatalog:
    """Catalog service bridging domain models and repository search."""

    def __init__(self, repository: EmojiRepository) -> None:
        self._repository = repository

    def search(self, query: str = "", category: str | None = None) -> Sequence[Emoji]:
        """Search emojis matching the provided query text and optional category."""
        return self._repository.search_emojis(query=query, category=category)

    def get_categories(self) -> Sequence[str]:
        """Return available emoji categories from repository."""
        return self._repository.get_categories()


__all__ = ["DomainEmojiCatalog", "EmojiCatalog", "EmojiSearchEngine"]
