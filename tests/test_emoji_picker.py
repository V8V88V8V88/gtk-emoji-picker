import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")

from gi.repository import Gio, Gtk

from emoji_picker import EmojiPicker
from emoji_repository import JsonEmojiRepository
from gtk_emoji_picker.gui.grid_view import EmojiGridView
from hotkey_service import HotkeyListener


def test_emojis_json_validity() -> None:
    emoji_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "emojis.json")
    assert os.path.exists(emoji_file)
    with open(emoji_file, encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, list)
    assert len(data) > 0
    for item in data:
        assert "emoji" in item
        assert "name" in item


def test_repository_list_and_search() -> None:
    repo = JsonEmojiRepository()
    all_emojis = repo.list_emojis()
    assert isinstance(all_emojis, list)
    assert len(all_emojis) > 0
    assert "category" in all_emojis[0]

    results = repo.search_emojis("heart")
    assert len(results) > 0
    for item in results:
        assert "heart" in item["name"].lower()


def test_emoji_picker_initialization() -> None:
    app = EmojiPicker()
    assert isinstance(app.emojis, list)
    assert len(app.emojis) > 0


def test_emoji_filtering_with_grid_view() -> None:
    app = EmojiPicker()
    app.emoji_list = EmojiGridView()
    app.populate_emoji_list("heart")
    assert len(app.filtered_emojis) > 0
    for item in app.filtered_emojis:
        assert "heart" in item["name"].lower()
    assert app.emoji_list.get_child_at_index(0) is not None


def test_search_debounce_schedules_and_coalesces() -> None:
    app = EmojiPicker(search_debounce_ms=250)

    assert app._search_timeout_id is None
    assert app._search_generation == 0

    with patch("emoji_picker.GLib.timeout_add", return_value=1234) as mock_timeout, patch(
        "emoji_picker.GLib.source_remove"
    ) as mock_remove:
        app.on_search_changed(MagicMock())
        app.on_search_changed(MagicMock())

    # Bursts of keystrokes schedule a single pending refresh
    assert mock_timeout.call_count == 2
    assert mock_remove.call_count == 1  # the first pending debounce was cancelled
    mock_timeout.assert_called_with(250, app._on_search_debounce_fired, 2)
    assert app._search_timeout_id == 1234
    assert app._search_generation == 2


def test_search_debounce_stale_generation_ignored() -> None:
    from gi.repository import GLib

    app = EmojiPicker()
    app.emoji_list = MagicMock()
    app.search_entry = Gtk.SearchEntry()
    app.search_entry.set_text("zzznone")

    app._search_generation = 7
    result = app._on_search_debounce_fired(6)

    assert result == GLib.SOURCE_REMOVE
    app.emoji_list.populate.assert_not_called()
    assert app._search_timeout_id is None


def test_search_debounce_fire_filters_grid_in_real_time() -> None:
    from gi.repository import GLib

    app = EmojiPicker()
    app.emoji_list = MagicMock()
    app.search_entry = Gtk.SearchEntry()
    app.search_entry.set_text("heart")

    app._search_generation = 3
    result = app._on_search_debounce_fired(3)

    assert result == GLib.SOURCE_REMOVE
    assert app._search_timeout_id is None
    assert len(app.filtered_emojis) > 0
    for item in app.filtered_emojis:
        assert "heart" in item["name"].lower()

    args, kwargs = app.emoji_list.populate.call_args
    assert args[0] == app.filtered_emojis
    assert kwargs["flat"] is True  # search results render in seamless flat mode


def test_clear_search_restores_default_category_view() -> None:
    app = EmojiPicker()
    app.emoji_list = MagicMock()

    # Typing a query renders results in flat search mode
    app.populate_emoji_list("heart")
    assert app.emoji_list.populate.call_args.kwargs["flat"] is True
    assert len(app.filtered_emojis) > 0

    # Clearing the query restores the default grouped category view
    app.emoji_list.populate.reset_mock()
    app.populate_emoji_list("")
    assert app.emoji_list.populate.call_args.kwargs["flat"] is False
    assert app.filtered_emojis == app.repository.list_emojis()


def test_reset_view_clears_search_and_category() -> None:
    app = EmojiPicker()
    app.search_entry = Gtk.SearchEntry()
    app.search_entry.set_text("heart")
    app.category_bar = MagicMock()
    app.emoji_list = MagicMock()

    app._reset_view()

    assert app.search_entry.get_text() == ""
    app.category_bar.set_active_category.assert_called_once_with(None)
    assert app.emoji_list.populate.call_args.kwargs["flat"] is False


def test_search_key_pressed_moves_focus_into_results() -> None:
    from gi.repository import Gdk

    app = EmojiPicker()
    grid = EmojiGridView()
    grid.populate(
        [
            {"emoji": "❤️", "name": "red heart", "category": "Symbols"},
            {"emoji": "🚀", "name": "rocket", "category": "Travel & Places"},
        ],
        flat=True,
    )
    app.emoji_list = grid

    # Down arrow moves keyboard focus into the first search result
    assert app._on_search_key_pressed(None, Gdk.KEY_Down, 0, None) is True
    assert grid.get_selected_row() is grid.get_child_at_index(0)

    # Other keys are not consumed by the search entry handler
    assert app._on_search_key_pressed(None, Gdk.KEY_Right, 0, None) is False

    # With no results the key is left unhandled
    empty = EmojiGridView()
    app.emoji_list = empty
    assert app._on_search_key_pressed(None, Gdk.KEY_Down, 0, None) is False


def test_hotkey_listener_instantiation() -> None:
    listener = HotkeyListener()
    assert listener.listener is None
    assert hasattr(listener, "start")
    assert hasattr(listener, "on_shortcut_activated")
    assert hasattr(listener, "launch_emoji_picker")


def test_repository_record_validation(tmp_path) -> None:
    bad_data = [
        {"emoji": "🔥 ", "name": " fire "},
        {"emoji": "", "name": "blank emoji"},
        {"emoji": "⭐", "name": "   "},
        {"emoji": 123, "name": "number emoji"},
        "not a dict",
        {"only_emoji": "🎉"},
    ]
    test_json = tmp_path / "test_emojis.json"
    test_json.write_text(json.dumps(bad_data), encoding="utf-8")

    repo = JsonEmojiRepository(str(test_json))
    emojis = repo.list_emojis()
    assert len(emojis) == 1
    assert emojis[0]["emoji"] == "🔥"
    assert emojis[0]["name"] == "fire"
    assert emojis[0]["category"] == "Smileys & Emotion"


def test_repository_query_validation() -> None:
    repo = JsonEmojiRepository()

    with pytest.raises(TypeError):
        repo.search_emojis(123)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        repo.search_emojis(["heart"])  # type: ignore[arg-type]

    assert repo.search_emojis(None) == repo.list_emojis()
    assert repo.search_emojis("   ") == repo.list_emojis()


def test_window_toggle_and_daemon_lifecycle() -> None:
    app = EmojiPicker(is_daemon=True)
    mock_window = gi.repository.Gtk.ApplicationWindow(application=app)
    app.window = mock_window

    mock_window.set_visible(True)
    app.toggle_window()
    assert not mock_window.get_visible()

    app.toggle_window()
    assert mock_window.get_visible()

    result = app._on_close_request(mock_window)
    assert result is True
    assert not mock_window.get_visible()

    app_standalone = EmojiPicker(is_daemon=False)
    app_standalone.window = mock_window
    standalone_result = app_standalone._on_close_request(mock_window)
    assert standalone_result is False
    assert app_standalone.window is None


def test_hotkey_listener_toggle_integration() -> None:
    mock_app = MagicMock()
    listener = HotkeyListener(picker_app=mock_app)

    with patch("gi.repository.GLib.idle_add") as mock_idle_add:
        listener.launch_emoji_picker()
        mock_idle_add.assert_called_once_with(mock_app.toggle_window)


def test_emoji_picker_handles_command_line() -> None:
    app = EmojiPicker()
    assert bool(app.get_flags() & Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

    mock_cl = MagicMock()
    mock_cl.get_arguments.return_value = ["gtk-emoji-picker", "--toggle"]
    with patch.object(app, "toggle_window") as mock_toggle:
        assert app.do_command_line(mock_cl) == 0
        mock_toggle.assert_called_once()

    mock_cl.get_arguments.return_value = ["gtk-emoji-picker"]
    with patch.object(app, "activate") as mock_activate:
        assert app.do_command_line(mock_cl) == 0
        mock_activate.assert_called_once()


def test_emoji_picker_toggle_window_states() -> None:
    app = EmojiPicker(is_daemon=True)
    mock_window = gi.repository.Gtk.ApplicationWindow(application=app)

    # Window exists and is visible -> toggle hides it
    mock_window.set_visible(True)
    app.window = mock_window
    app.toggle_window()
    assert not mock_window.get_visible()

    # Window exists and is hidden -> toggle presents and focuses search
    app.search_entry = MagicMock()
    app.toggle_window()
    assert mock_window.get_visible()
    app.search_entry.grab_focus.assert_called_once()

    # No window -> activate builds and shows it
    app.window = None
    with patch.object(app, "activate") as mock_activate:
        app.toggle_window()
        mock_activate.assert_called_once()


def test_hotkey_listener_launch_appends_toggle_flag() -> None:
    listener = HotkeyListener()
    with (
        patch("os.path.isfile", return_value=True),
        patch("os.access", return_value=True),
        patch("subprocess.Popen") as mock_popen,
    ):
        listener.launch_emoji_picker()
        command_args = mock_popen.call_args[0][0]
        assert "--toggle" in command_args
        assert command_args[-1] == "--toggle"


def test_clipboard_service_copy_text() -> None:
    from gtk_emoji_picker.infrastructure.clipboard import ClipboardService

    mock_gdk_clipboard = MagicMock()
    mock_display = MagicMock()
    mock_display.get_clipboard.return_value = mock_gdk_clipboard

    service = ClipboardService(display=mock_display)
    result = service.copy_text("🚀")

    assert result is True
    mock_gdk_clipboard.set.assert_called_once_with("🚀")


def test_auto_paste_service_executes_custom_executor() -> None:
    from gtk_emoji_picker.infrastructure.clipboard import AutoPasteService

    executed: list[bool] = []

    def custom_paste() -> bool:
        executed.append(True)
        return True

    service = AutoPasteService(delay_seconds=0, paste_executor=custom_paste)
    result = service.paste()

    assert result is True
    assert len(executed) == 1


def test_emoji_picker_copy_emoji_and_close() -> None:
    app = EmojiPicker(is_daemon=False)
    mock_window = MagicMock()
    app.window = mock_window

    mock_clipboard = MagicMock()
    mock_display = MagicMock()
    mock_display.get_clipboard.return_value = mock_clipboard

    with patch("gi.repository.Gdk.Display.get_default", return_value=mock_display):
        app.copy_emoji_and_close("🎉")
        mock_clipboard.set.assert_called_once_with("🎉")
        mock_window.close.assert_called_once()

    mock_window.reset_mock()
    with patch("gi.repository.Gdk.Display.get_default", return_value=None):
        app.copy_emoji_and_close("🎉")
        mock_window.close.assert_called_once()


def test_emoji_picker_gtk_lifecycle_and_events() -> None:
    from gi.repository import Gdk

    app = EmojiPicker()
    app.do_activate()

    assert app.window is not None
    assert isinstance(app.search_entry, Gtk.SearchEntry)
    assert isinstance(app.emoji_list, EmojiGridView)
    assert len(app.filtered_emojis) > 0

    app.search_entry.set_text("test")
    app.do_activate()
    assert app.search_entry.get_text() == ""

    mock_window = MagicMock()
    app.window = mock_window
    assert app.on_key_pressed(None, Gdk.KEY_Escape, 0, None) is True
    mock_window.close.assert_called_once()
    assert app.on_key_pressed(None, Gdk.KEY_a, 0, None) is False

    app.window = None
    with patch.object(app, "activate") as mock_activate:
        app.toggle_window()
        mock_activate.assert_called_once()

    app.do_activate()
    app.search_entry.set_text("smile")
    app.populate_emoji_list("smile")
    assert len(app.filtered_emojis) > 0

    mock_row = MagicMock()
    mock_row.get_index.return_value = 0
    with patch.object(app.emoji_list, "get_selected_row", return_value=mock_row):
        with patch.object(app, "copy_emoji_and_close") as mock_copy:
            app.on_search_activate(app.search_entry)
            mock_copy.assert_called_once()

    with patch.object(app.emoji_list, "get_selected_row", return_value=None):
        with patch.object(app, "copy_emoji_and_close") as mock_copy:
            app.on_search_activate(app.search_entry)
            mock_copy.assert_called_once_with(app.filtered_emojis[0]["emoji"])

    app.filtered_emojis = []
    with patch.object(app.emoji_list, "get_selected_row", return_value=None):
        with patch.object(app, "copy_emoji_and_close") as mock_copy:
            app.on_search_activate(app.search_entry)
            mock_copy.assert_not_called()

    app.filtered_emojis = [{"emoji": "🔥", "name": "fire", "category": "Objects"}]
    mock_selected_row = MagicMock()
    mock_selected_row.get_index.return_value = 0
    with patch.object(app, "copy_emoji_and_close") as mock_copy:
        app.on_emoji_selected(app.emoji_list, mock_selected_row)
        mock_copy.assert_called_once_with("🔥")

    mock_bad_row = MagicMock()
    mock_bad_row.get_index.side_effect = Exception("Invalid row")
    app.on_emoji_selected(app.emoji_list, mock_bad_row)


def test_populate_emoji_list_fallback_loop() -> None:
    app = EmojiPicker()

    class DummyListBox:
        def __init__(self) -> None:
            self.children = [MagicMock(), MagicMock()]

        def get_first_child(self):
            return self.children[0] if self.children else None

        def remove(self, child) -> None:
            if child in self.children:
                self.children.remove(child)

        def append(self, item) -> None:
            return None

    dummy_listbox = DummyListBox()
    app.emoji_list = dummy_listbox
    app.populate_emoji_list()
    assert len(dummy_listbox.children) == 0


def test_emoji_picker_main_function() -> None:
    with patch("emoji_picker.EmojiPicker.run", return_value=0) as mock_run:
        from emoji_picker import main

        assert main() == 0
        mock_run.assert_called_once()


def test_clipboard_and_auto_paste_service_edge_cases() -> None:
    from gtk_emoji_picker.infrastructure.clipboard import AutoPasteService, ClipboardService

    service = ClipboardService(display=None)
    with patch("gi.repository.Gdk.Display.get_default", return_value=None):
        with patch.object(service, "_copy_with_wl_copy", return_value=False):
            with patch.object(service, "_copy_with_xclip", return_value=False):
                with patch.object(service, "_copy_with_xsel", return_value=False):
                    assert service.get_clipboard() is None
                    assert service.copy_text("test") is False

    mock_clip = MagicMock()
    mock_clip.set.side_effect = Exception("Set failed")
    mock_display = MagicMock()
    mock_display.get_clipboard.return_value = mock_clip
    failing_service = ClipboardService(display=mock_display)
    with patch.object(failing_service, "_copy_with_wl_copy", return_value=False):
        with patch.object(failing_service, "_copy_with_xclip", return_value=False):
            with patch.object(failing_service, "_copy_with_xsel", return_value=False):
                assert failing_service.copy_text("test") is False

    # Test CLI clipboard fallbacks (wl-copy, xclip, xsel)
    clip_service = ClipboardService(display=None)
    with patch("gi.repository.Gdk.Display.get_default", return_value=None):
        with patch.object(clip_service, "_copy_with_wl_copy", return_value=True) as mock_wl:
            assert clip_service.copy_text("🚀") is True
            mock_wl.assert_called_once_with("🚀")

        with patch.object(clip_service, "_copy_with_wl_copy", return_value=False):
            with patch.object(clip_service, "_copy_with_xclip", return_value=True) as mock_xc:
                assert clip_service.copy_text("🚀") is True
                mock_xc.assert_called_once_with("🚀")

        with patch.object(clip_service, "_copy_with_wl_copy", return_value=False):
            with patch.object(clip_service, "_copy_with_xclip", return_value=False):
                with patch.object(clip_service, "_copy_with_xsel", return_value=True) as mock_xs:
                    assert clip_service.copy_text("🚀") is True
                    mock_xs.assert_called_once_with("🚀")

    # Test internal helper execution errors for copy fallbacks
    with patch("subprocess.run", side_effect=subprocess.SubprocessError("wl-copy missing")):
        assert clip_service._copy_with_wl_copy("test") is False

    with patch("subprocess.Popen", side_effect=subprocess.SubprocessError("xclip missing")):
        assert clip_service._copy_with_xclip("test") is False

    # Test xclip/xsel process returncode success and failure
    mock_proc_ok = MagicMock()
    mock_proc_ok.communicate.return_value = (b"", b"")
    mock_proc_ok.returncode = 0
    with patch("subprocess.Popen", return_value=mock_proc_ok):
        assert clip_service._copy_with_xclip("test") is True
        assert clip_service._copy_with_xsel("test") is True

    mock_proc_fail = MagicMock()
    mock_proc_fail.communicate.return_value = (b"", b"")
    mock_proc_fail.returncode = 1
    with patch("subprocess.Popen", return_value=mock_proc_fail):
        assert clip_service._copy_with_xclip("test") is False
        assert clip_service._copy_with_xsel("test") is False

    with patch("subprocess.Popen", side_effect=subprocess.SubprocessError("xsel missing")):
        assert clip_service._copy_with_xsel("test") is False

    auto_paste = AutoPasteService(delay_seconds=0)

    # Test Wayland fallback order: ydotool -> wtype -> pynput -> xdotool
    with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}):
        with patch.object(auto_paste, "_paste_with_ydotool", return_value=True) as mock_yd:
            assert auto_paste.paste() is True
            mock_yd.assert_called_once()

    with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}):
        with patch.object(auto_paste, "_paste_with_ydotool", return_value=False):
            with patch.object(auto_paste, "_paste_with_wtype", return_value=True) as mock_wt:
                assert auto_paste.paste() is True
                mock_wt.assert_called_once()

    with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}):
        with patch.object(auto_paste, "_paste_with_ydotool", return_value=False):
            with patch.object(auto_paste, "_paste_with_wtype", return_value=False):
                with patch.object(auto_paste, "_paste_with_pynput", return_value=True) as mock_pyn:
                    assert auto_paste.paste() is True
                    mock_pyn.assert_called_once()

    with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}):
        with patch.object(auto_paste, "_paste_with_ydotool", return_value=False):
            with patch.object(auto_paste, "_paste_with_wtype", return_value=False):
                with patch.object(auto_paste, "_paste_with_pynput", return_value=False):
                    with patch.object(
                        auto_paste, "_paste_with_xdotool", return_value=True
                    ) as mock_xd:
                        assert auto_paste.paste() is True
                        mock_xd.assert_called_once()

    # Test X11 fallback order: xdotool -> ydotool -> pynput -> wtype
    with patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"}):
        with patch.object(auto_paste, "_paste_with_xdotool", return_value=True) as mock_xdotool:
            assert auto_paste.paste() is True
            mock_xdotool.assert_called_once()

    with patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"}):
        with patch.object(auto_paste, "_paste_with_xdotool", return_value=False):
            with patch.object(auto_paste, "_paste_with_ydotool", return_value=True) as mock_yd:
                assert auto_paste.paste() is True
                mock_yd.assert_called_once()

    with patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"}):
        with patch.object(auto_paste, "_paste_with_xdotool", return_value=False):
            with patch.object(auto_paste, "_paste_with_ydotool", return_value=False):
                with patch.object(auto_paste, "_paste_with_pynput", return_value=True) as mock_pyn:
                    assert auto_paste.paste() is True
                    mock_pyn.assert_called_once()

    with patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"}):
        with patch.object(auto_paste, "_paste_with_xdotool", return_value=False):
            with patch.object(auto_paste, "_paste_with_ydotool", return_value=False):
                with patch.object(auto_paste, "_paste_with_pynput", return_value=False):
                    with patch.object(
                        auto_paste, "_paste_with_wtype", return_value=True
                    ) as mock_wt:
                        assert auto_paste.paste() is True
                        mock_wt.assert_called_once()

    with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}):
        with patch.object(auto_paste, "_paste_with_ydotool", return_value=False):
            with patch.object(auto_paste, "_paste_with_wtype", return_value=False):
                with patch.object(auto_paste, "_paste_with_pynput", return_value=False):
                    with patch.object(auto_paste, "_paste_with_xdotool", return_value=False):
                        assert auto_paste.paste() is False

    with patch("subprocess.run", return_value=None):
        assert auto_paste._paste_with_ydotool() is True
        assert auto_paste._paste_with_wtype() is True
        assert auto_paste._paste_with_xdotool() is True

    mock_controller = MagicMock()
    with patch("pynput.keyboard.Controller", return_value=mock_controller):
        assert auto_paste._paste_with_pynput() is True

    with patch("subprocess.run", side_effect=subprocess.SubprocessError("ydotool missing")):
        assert auto_paste._paste_with_ydotool() is False

    with patch("subprocess.run", side_effect=subprocess.SubprocessError("wtype missing")):
        assert auto_paste._paste_with_wtype() is False

    with patch("subprocess.run", side_effect=subprocess.SubprocessError("xdotool missing")):
        assert auto_paste._paste_with_xdotool() is False

    with patch("builtins.__import__", side_effect=ImportError("pynput missing")):
        assert auto_paste._paste_with_pynput() is False
