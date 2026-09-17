"""Tests for Emoji data model, providers, repository, and search engine service."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from gtk_emoji_picker.domain.models import Emoji
from gtk_emoji_picker.infrastructure.emoji_provider import (
    DictEmojiProvider,
    InMemoryEmojiProvider,
    JsonEmojiProvider,
)
from gtk_emoji_picker.services.emoji_catalog import DomainEmojiCatalog
from gtk_emoji_picker.services.emoji_search_engine import EmojiSearchEngine


def test_emoji_domain_model_attributes_and_immutability() -> None:
    emoji = Emoji(
        glyph="👍",
        name="thumbs up",
        category="People & Body",
        keywords=("like", "approve", "hand"),
        unicode_version="1.0",
        skin_tone_variants=("👍🏻", "👍🏼", "👍🏽", "👍🏾", "👍🏿"),
        annotations=("hand", "thumb", "+1"),
        shortcodes=(":thumbsup:", ":+1:"),
    )
    assert emoji.glyph == "👍"
    assert emoji.name == "thumbs up"
    assert emoji.category == "People & Body"
    assert emoji.keywords == ("like", "approve", "hand")
    assert emoji.unicode_version == "1.0"
    assert emoji.skin_tone_variants == ("👍🏻", "👍🏼", "👍🏽", "👍🏾", "👍🏿")
    assert emoji.annotations == ("hand", "thumb", "+1")
    assert emoji.shortcodes == (":thumbsup:", ":+1:")
    assert hash(emoji) is not None

    with pytest.raises(AttributeError):
        emoji.glyph = "👎"  # type: ignore

    # Test serialization methods
    d = emoji.to_dict()
    assert d["glyph"] == "👍"
    assert d["name"] == "thumbs up"
    assert d["keywords"] == ["like", "approve", "hand"]
    assert d["skin_tone_variants"] == ["👍🏻", "👍🏼", "👍🏽", "👍🏾", "👍🏿"]
    assert d["annotations"] == ["hand", "thumb", "+1"]
    assert d["shortcodes"] == [":thumbsup:", ":+1:"]

    parsed = Emoji.from_dict(d)
    assert parsed == emoji

    # Test CLDR dataset structure parsing (character, description, annotations, variants dict)
    cldr_item = {
        "character": "👋",
        "description": "waving hand",
        "category": "People & Body",
        "annotations": ["wave", "hand", "goodbye"],
        "shortcodes": [":wave:"],
        "variants": {
            "light": "👋🏻",
            "medium-light": "👋🏼",
            "medium": "👋🏽",
        },
    }
    cldr_parsed = Emoji.from_dict(cldr_item)
    assert cldr_parsed is not None
    assert cldr_parsed.glyph == "👋"
    assert cldr_parsed.name == "waving hand"
    assert cldr_parsed.annotations == ("wave", "hand", "goodbye")
    assert cldr_parsed.shortcodes == (":wave:",)
    assert cldr_parsed.skin_tone_variants == ("👋🏻", "👋🏼", "👋🏽")

    # Test invalid dict parsing
    assert Emoji.from_dict({}) is None
    assert Emoji.from_dict({"emoji": "😀"}) is None  # Missing name


def test_in_memory_and_dict_emoji_providers() -> None:
    e1 = Emoji("😀", "grinning face")
    mem_provider = InMemoryEmojiProvider([e1])
    assert mem_provider.load_emojis() == (e1,)

    records: list[dict[str, Any]] = [
        {"glyph": "⭐", "name": "star", "category": "Symbols", "keywords": ["bright", "sky"]},
        {"invalid": "item"},
    ]
    dict_provider = DictEmojiProvider(records)
    dict_emojis = dict_provider.load_emojis()
    assert len(dict_emojis) == 1
    assert dict_emojis[0].glyph == "⭐"
    assert dict_emojis[0].category == "Symbols"


def test_json_emoji_provider_parsing_and_fallback(tmp_path: Path) -> None:
    sample_data = [
        {
            "emoji": "🎉",
            "name": "party popper",
            "category": "Activities",
            "keywords": ["celebrate", "party"],
            "unicode_version": "0.6",
        },
        {
            "glyph": "🔥",
            "name": "fire",
            "keywords": "hot, flame",
        },
        {"invalid": "record"},
    ]
    test_json = tmp_path / "custom_emojis.json"
    test_json.write_text(json.dumps(sample_data), encoding="utf-8")

    provider = JsonEmojiProvider(json_path=test_json)
    emojis = provider.load_emojis()

    assert len(emojis) == 2
    assert emojis[0].glyph == "🎉"
    assert emojis[0].category == "Activities"
    assert emojis[0].keywords == ("celebrate", "party")
    assert emojis[1].glyph == "🔥"
    assert emojis[1].category == "Smileys & Emotion"
    assert emojis[1].keywords == ("hot", "flame")

    # Non-existent file uses fallback
    bad_provider = JsonEmojiProvider(json_path=tmp_path / "non_existent.json")
    fallback_emojis = bad_provider.load_emojis()
    assert len(fallback_emojis) > 0


def test_emoji_search_engine_indexing_and_search() -> None:
    emojis = [
        Emoji("😀", "grinning face", "Smileys & Emotion", ("happy", "smile")),
        Emoji("❤️", "red heart", "Symbols", ("love", "heart")),
        Emoji("💖", "sparkling heart", "Symbols", ("love", "sparkle", "heart")),
        Emoji("🐶", "dog face", "Animals & Nature", ("pet", "dog", "puppy")),
    ]

    engine = EmojiSearchEngine(emojis=emojis)
    assert len(engine.get_emojis()) == 4

    # Test category listing
    categories = engine.get_categories()
    assert "Smileys & Emotion" in categories
    assert "Symbols" in categories
    assert "Animals & Nature" in categories

    # Fast glyph lookup
    assert engine.get_emoji_by_glyph("❤️") == emojis[1]
    assert engine.get_emoji_by_glyph("❌") is None

    # Keyword search
    heart_matches = engine.search("heart")
    assert len(heart_matches) == 2
    assert {e.glyph for e in heart_matches} == {"❤️", "💖"}

    # Exact token / keyword match ranking
    love_matches = engine.search("love")
    assert len(love_matches) == 2

    # Category filter combined with search
    symbols_heart = engine.search("heart", category="Symbols")
    assert len(symbols_heart) == 2

    no_matches = engine.search("heart", category="Animals & Nature")
    assert len(no_matches) == 0

    # Glyph exact search
    dog_glyph = engine.search("🐶")
    assert len(dog_glyph) == 1
    assert dog_glyph[0].name == "dog face"

    # None or empty query returns all items in filter
    assert len(engine.search(None)) == 4
    assert len(engine.search("", category="Symbols")) == 2


def test_emoji_domain_model_dict_parsing_edge_cases() -> None:
    # Test blank category falling back to default
    d1 = {"emoji": "🔥", "name": "fire", "category": "   "}
    e1 = Emoji.from_dict(d1, default_category="Custom Category")
    assert e1 is not None
    assert e1.category == "Custom Category"

    # Test keyword list with non-string elements ignored
    d2 = {"emoji": "⭐", "name": "star", "keywords": ["sparkle", 123, None, "  "]}
    e2 = Emoji.from_dict(d2)
    assert e2 is not None
    assert e2.keywords == ("sparkle",)

    # Test unicode version default and fallback
    d3 = {"emoji": "🎉", "name": "party", "unicode_version": "  "}
    e3 = Emoji.from_dict(d3)
    assert e3 is not None
    assert e3.unicode_version == "1.0"


def test_base_emoji_provider_abstract() -> None:
    from gtk_emoji_picker.infrastructure.emoji_provider import BaseEmojiProvider

    class IncompleteProvider(BaseEmojiProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()  # type: ignore[abstract]


def test_json_emoji_provider_edge_cases(tmp_path: Path) -> None:
    # Default json_path (None) initializes to emojis.json
    default_provider = JsonEmojiProvider()
    assert default_provider.json_path.name == "emojis.json"

    # Non-list JSON structure triggers fallback
    not_list_file = tmp_path / "not_list.json"
    not_list_file.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    p1 = JsonEmojiProvider(json_path=not_list_file)
    assert p1.load_emojis() == JsonEmojiProvider.FALLBACK_EMOJIS

    # Empty list JSON triggers fallback
    empty_list_file = tmp_path / "empty.json"
    empty_list_file.write_text("[]", encoding="utf-8")
    p2 = JsonEmojiProvider(json_path=empty_list_file)
    assert p2.load_emojis() == JsonEmojiProvider.FALLBACK_EMOJIS

    # List with no valid records triggers fallback
    invalid_records_file = tmp_path / "invalid.json"
    invalid_records_file.write_text(json.dumps([{"invalid": "item"}]), encoding="utf-8")
    p3 = JsonEmojiProvider(json_path=invalid_records_file)
    assert p3.load_emojis() == JsonEmojiProvider.FALLBACK_EMOJIS

    # Corrupt JSON syntax triggers fallback
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{bad json...", encoding="utf-8")
    p4 = JsonEmojiProvider(json_path=corrupt_file)
    assert p4.load_emojis() == JsonEmojiProvider.FALLBACK_EMOJIS


def test_emoji_search_engine_scoring_and_provider_init() -> None:
    emojis = [
        Emoji("😀", "grinning face", "Smileys & Emotion", ("happy", "smile")),
        Emoji("🔥", "fire", "Smileys & Emotion", ("hot", "flame")),
        Emoji("❤️", "red heart", "Symbols", ("love", "heart")),
        Emoji("💖", "sparkling heart", "Symbols", ("heart", "sparkle")),
        Emoji("🐶", "dog face", "Animals & Nature", ("dog", "puppy")),
        Emoji("🐶‍🦺", "service dog", "Animals & Nature", ("dog", "guide")),
    ]

    # Initialize via provider parameter
    mem_provider = InMemoryEmojiProvider(emojis)
    engine = EmojiSearchEngine(provider=mem_provider)
    assert len(engine.get_emojis()) == 6

    # Test unknown category return value
    assert engine.search("fire", category="NonExistent") == ()

    # Test get_emoji_by_glyph edge cases
    assert engine.get_emoji_by_glyph("") is None
    assert engine.get_emoji_by_glyph("   ") is None

    # Test scoring: exact name match vs exact keyword match
    # 'fire' is exact name for 🔥 (score 100)
    res_fire = engine.search("fire")
    assert res_fire[0].glyph == "🔥"

    # 'flame' is exact keyword for 🔥 (score 90)
    res_flame = engine.search("flame")
    assert res_flame[0].glyph == "🔥"

    # 'red' is name prefix for 'red heart' (score 80)
    res_red = engine.search("red")
    assert res_red[0].glyph == "❤️"

    # 'gu' is keyword prefix for 'guide' in 'service dog' (score 70)
    res_gu = engine.search("gu")
    assert res_gu[0].glyph == "🐶‍🦺"

    # Substring in keyword matching
    # 'arkle' is substring of 'sparkle' keyword in 'sparkling heart'
    res_sub = engine.search("arkle")
    assert len(res_sub) == 1
    assert res_sub[0].name == "sparkling heart"

    # Substring in name matching
    # 'ark' is substring of 'sparkling' in name
    res_sub_name = engine.search("ark")
    assert len(res_sub_name) == 1
    assert res_sub_name[0].name == "sparkling heart"


def test_emoji_search_engine_annotations_shortcodes_and_skin_tones() -> None:
    emojis = [
        Emoji(
            glyph="👍",
            name="thumbs up",
            category="People & Body",
            keywords=("like", "approve"),
            skin_tone_variants=("👍🏻", "👍🏼", "👍🏽", "👍🏾", "👍🏿"),
            annotations=("hand", "thumb", "gesture"),
            shortcodes=(":thumbsup:", ":+1:"),
        ),
        Emoji(
            glyph="👋",
            name="waving hand",
            category="People & Body",
            annotations=("wave", "greeting", "hello"),
            shortcodes=(":wave:",),
        ),
    ]

    engine = EmojiSearchEngine(emojis=emojis)

    # Search by shortcode
    sc_match = engine.search(":thumbsup:")
    assert len(sc_match) == 1
    assert sc_match[0].glyph == "👍"

    # Search by shortcode without colons
    sc_no_colon = engine.search("thumbsup")
    assert len(sc_no_colon) == 1
    assert sc_no_colon[0].glyph == "👍"

    # Search by annotation
    ann_match = engine.search("greeting")
    assert len(ann_match) == 1
    assert ann_match[0].glyph == "👋"

    # Skin tone variant inspection
    thumb = engine.get_emoji_by_glyph("👍")
    assert thumb is not None
    assert "👍🏽" in thumb.skin_tone_variants


def test_domain_emoji_catalog_integration() -> None:
    mock_repo = MagicMock()
    mock_repo.search_emojis.return_value = [
        Emoji("❤️", "red heart"),
    ]
    mock_repo.get_categories.return_value = ["Smileys & Emotion", "Symbols"]

    catalog = DomainEmojiCatalog(repository=mock_repo)
    assert list(catalog.get_categories()) == ["Smileys & Emotion", "Symbols"]

    res = catalog.search("heart", category="Symbols")
    mock_repo.search_emojis.assert_called_once_with(query="heart", category="Symbols")
    assert len(res) == 1
    assert res[0].glyph == "❤️"


def test_json_emoji_repository_extended_fields_and_validation(tmp_path: Path) -> None:
    from emoji_repository import JsonEmojiRepository

    data = [
        {
            "character": "👍",
            "description": "thumbs up",
            "category": "People & Body",
            "keywords": ["like", "approve"],
            "annotations": ["hand", "+1"],
            "shortcodes": [":thumbsup:"],
            "variants": ["👍🏻", "👍🏼"],
        }
    ]
    test_json = tmp_path / "extended.json"
    test_json.write_text(json.dumps(data), encoding="utf-8")

    repo = JsonEmojiRepository(str(test_json))

    # Test get_categories
    categories = repo.get_categories()
    assert "People & Body" in categories

    # Test list_emojis with extended fields
    all_emojis = repo.list_emojis()
    assert len(all_emojis) == 1
    item = all_emojis[0]
    assert item["emoji"] == "👍"
    assert item["name"] == "thumbs up"
    assert item["category"] == "People & Body"
    assert item["keywords"] == ["like", "approve"]
    assert item["annotations"] == ["hand", "+1"]
    assert item["shortcodes"] == [":thumbsup:"]
    assert item["skin_tone_variants"] == ["👍🏻", "👍🏼"]

    # Test search_emojis with extended fields
    searched = repo.search_emojis("thumbsup")
    assert len(searched) == 1
    assert searched[0]["emoji"] == "👍"

    # Test invalid query type error handling
    with pytest.raises(TypeError):
        repo.search_emojis(123)  # type: ignore

    # Test _validate_record helper
    valid_record = repo._validate_record({"character": "🎉", "label": "party popper"})
    assert valid_record is not None
    assert valid_record["emoji"] == "🎉"
    assert valid_record["name"] == "party popper"
    assert valid_record["category"] == "Smileys & Emotion"

    invalid_record = repo._validate_record({"invalid": "data"})
    assert invalid_record is None
