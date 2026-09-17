"""Emoji Indexing & Search Engine Service."""

import re
from collections import defaultdict
from collections.abc import Sequence

from gtk_emoji_picker.domain.models import Emoji, EmojiProvider


class EmojiSearchEngine:
    """Fast indexed search engine for Emoji domain objects.

    Supports:
    - Pre-indexed lookup by tokens (name + keywords)
    - Category filtering
    - Exact and prefix matching with relevance scoring
    - Fast sub-string token matching
    """

    def __init__(
        self,
        provider: EmojiProvider | None = None,
        emojis: Sequence[Emoji] | None = None,
    ) -> None:
        self._emojis: list[Emoji] = []
        self._categories: list[str] = []
        self._token_index: dict[str, set[int]] = defaultdict(set)
        self._category_index: dict[str, set[int]] = defaultdict(set)
        self._glyph_index: dict[str, Emoji] = {}

        if emojis is not None:
            self.set_emojis(emojis)
        elif provider is not None:
            self.set_emojis(provider.load_emojis())

    def set_emojis(self, emojis: Sequence[Emoji]) -> None:
        """Build search index from the given emoji sequence."""
        self._emojis = list(emojis)
        self._token_index.clear()
        self._category_index.clear()
        self._glyph_index.clear()

        categories_seen: set[str] = set()

        for idx, emoji in enumerate(self._emojis):
            # Index by glyph for O(1) exact lookup
            self._glyph_index[emoji.glyph] = emoji

            # Index by category
            self._category_index[emoji.category].add(idx)
            if emoji.category not in categories_seen:
                categories_seen.add(emoji.category)

            # Tokenize name, keywords, annotations, and shortcodes
            tokens = self._tokenize(emoji.name)
            for kw in emoji.keywords:
                tokens.update(self._tokenize(kw))
            for ann in emoji.annotations:
                tokens.update(self._tokenize(ann))
            for sc in emoji.shortcodes:
                tokens.update(self._tokenize(sc.strip(":")))

            for token in tokens:
                self._token_index[token].add(idx)

        # Preserve sorted order for categories
        self._categories = sorted(categories_seen)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Split text into lowercase alphanumeric tokens."""
        return set(re.findall(r"\w+", text.lower()))

    def get_emojis(self) -> Sequence[Emoji]:
        """Return sequence of all indexed emojis."""
        return tuple(self._emojis)

    def get_categories(self) -> Sequence[str]:
        """Return list of available emoji categories."""
        return tuple(self._categories)

    def get_emoji_by_glyph(self, glyph: str) -> Emoji | None:
        """Fast O(1) lookup for an emoji by its glyph string."""
        return self._glyph_index.get(glyph.strip()) if glyph else None

    def search(self, query: str | None = "", category: str | None = None) -> Sequence[Emoji]:
        """Search emojis matching query string and/or category filter.

        Scoring hierarchy:
        1. Exact match on name or glyph
        2. Prefix match on name or keywords
        3. Token match count & token coverage
        4. Substring match
        """
        if category and category not in self._category_index:
            return ()

        # Candidate indices set based on category filter
        if category:
            candidate_indices = set(self._category_index[category])
        else:
            candidate_indices = set(range(len(self._emojis)))

        raw_query = "" if query is None else str(query)
        q_clean = raw_query.strip().lower()
        if not q_clean:
            return tuple(self._emojis[i] for i in sorted(candidate_indices))

        # Check if query is an exact single emoji glyph
        if raw_query.strip() in self._glyph_index:
            exact_emoji = self._glyph_index[raw_query.strip()]
            if not category or exact_emoji.category == category:
                return (exact_emoji,)

        query_tokens = self._tokenize(q_clean)

        scored_matches: list[tuple[float, int, Emoji]] = []

        for idx in candidate_indices:
            emoji = self._emojis[idx]
            score = self._score_emoji(emoji, q_clean, query_tokens)
            if score > 0:
                scored_matches.append((score, idx, emoji))

        # Sort by score descending, then original index ascending for stability
        scored_matches.sort(key=lambda item: (-item[0], item[1]))

        return tuple(item[2] for item in scored_matches)

    def _score_emoji(self, emoji: Emoji, q_clean: str, query_tokens: set[str]) -> float:
        """Calculate match score for an emoji against a search query."""
        name_lower = emoji.name.lower()

        # Exact name match (highest priority)
        if name_lower == q_clean:
            return 100.0

        # Exact match on shortcodes, keywords, or annotations
        q_sc = q_clean.strip(":")
        if any(sc.strip(":").lower() == q_sc for sc in emoji.shortcodes):
            return 95.0

        if any(kw.lower() == q_clean for kw in emoji.keywords) or any(
            ann.lower() == q_clean for ann in emoji.annotations
        ):
            return 90.0

        # Name starts with query
        if name_lower.startswith(q_clean):
            return 80.0

        # Any keyword, annotation, or shortcode starts with query
        if (
            any(kw.lower().startswith(q_clean) for kw in emoji.keywords)
            or any(ann.lower().startswith(q_clean) for ann in emoji.annotations)
            or any(sc.strip(":").lower().startswith(q_sc) for sc in emoji.shortcodes)
        ):
            return 70.0

        score = 0.0
        # Token matching
        if query_tokens:
            emoji_tokens = self._tokenize(emoji.name)
            for kw in emoji.keywords:
                emoji_tokens.update(self._tokenize(kw))
            for ann in emoji.annotations:
                emoji_tokens.update(self._tokenize(ann))
            for sc in emoji.shortcodes:
                emoji_tokens.update(self._tokenize(sc.strip(":")))

            matched_tokens = query_tokens.intersection(emoji_tokens)
            if matched_tokens:
                # Base token score proportional to matching ratio
                score += (len(matched_tokens) / len(query_tokens)) * 50.0

                # All query tokens matched bonus
                if len(matched_tokens) == len(query_tokens):
                    score += 15.0

                # Additional weight for prefix token matches
                for q_tok in query_tokens:
                    if any(e_tok.startswith(q_tok) for e_tok in emoji_tokens):
                        score += 5.0

        # Substring match in name, keywords, annotations, or shortcodes
        if q_clean in name_lower:
            score += 20.0
        elif (
            any(q_clean in kw.lower() for kw in emoji.keywords)
            or any(q_clean in ann.lower() for ann in emoji.annotations)
            or any(q_sc in sc.strip(":").lower() for sc in emoji.shortcodes)
        ):
            score += 15.0
        else:
            # Fuzzy prefix / stem matching (e.g., 'smile' matching 'smiling')
            emoji_tokens = self._tokenize(emoji.name)
            for kw in emoji.keywords:
                emoji_tokens.update(self._tokenize(kw))
            for ann in emoji.annotations:
                emoji_tokens.update(self._tokenize(ann))
            for e_tok in emoji_tokens:
                if len(q_clean) >= 4 and len(e_tok) >= 4 and e_tok[:4] == q_clean[:4]:
                    score += 15.0
                    break

        return score


__all__ = ["EmojiSearchEngine"]
