"""Tests for domain models, catalog services, and entry points."""

from unittest.mock import MagicMock, patch

import pytest

from gtk_emoji_picker.domain.models import Emoji
from gtk_emoji_picker.services.emoji_catalog import DomainEmojiCatalog


def test_emoji_domain_model() -> None:
    emoji = Emoji(glyph="😀", name="grinning face")
    assert emoji.glyph == "😀"
    assert emoji.name == "grinning face"
    assert (ishashable := hash(emoji) is not None)
    assert ishashable

    with pytest.raises(AttributeError):
        emoji.glyph = "😁"  # type: ignore # Immutable frozen dataclass


def test_domain_emoji_catalog_search() -> None:
    mock_repo = MagicMock()
    mock_repo.search_emojis.return_value = [
        Emoji(glyph="❤️", name="red heart"),
        Emoji(glyph="💖", name="sparkling heart"),
    ]

    catalog = DomainEmojiCatalog(repository=mock_repo)
    results = catalog.search("heart")

    mock_repo.search_emojis.assert_called_once_with(query="heart", category=None)
    assert len(results) == 2

    assert results[0].glyph == "❤️"
    assert results[1].name == "sparkling heart"


def test_main_entrypoint() -> None:
    with patch("emoji_picker.main", return_value=0) as mock_picker_main:
        from gtk_emoji_picker.__main__ import main

        exit_code = main()
        assert exit_code == 0
        mock_picker_main.assert_called_once()

    with patch("emoji_picker.main", return_value=None):
        from gtk_emoji_picker.__main__ import main

        exit_code = main()
        assert exit_code == 0


def test_shortcut_daemon_entrypoint() -> None:
    with patch(
        "gtk_emoji_picker.infrastructure.shortcut_daemon.ShortcutDaemon.run",
        return_value=0,
    ) as mock_daemon_run:
        from gtk_emoji_picker.infrastructure.shortcut_daemon import main

        exit_code = main()
        assert exit_code == 0
        mock_daemon_run.assert_called_once()


def test_pkg_main_module_execution() -> None:
    with patch("emoji_picker.main", return_value=0):
        with patch("sys.exit") as mock_exit:
            import runpy

            runpy.run_module("gtk_emoji_picker", run_name="__main__")
            mock_exit.assert_called_once_with(0)
