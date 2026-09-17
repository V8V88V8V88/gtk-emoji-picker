"""Unit tests for Global Shortcut Keybinding Listener and backends."""

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import gi

gi.require_version("Gio", "2.0")
import pytest
from gi.repository import Gio

from gtk_emoji_picker.infrastructure.shortcut_backends import (
    BaseShortcutListener,
    KeybinderShortcutListener,
    PortalShortcutListener,
    PynputShortcutListener,
    get_backend_candidates,
    select_best_backend,
)
from gtk_emoji_picker.infrastructure.shortcut_daemon import ShortcutDaemon
from hotkey_service import HotkeyListener


class DummyBackend(BaseShortcutListener):
    def __init__(self, shortcut: str = "Meta+.", available: bool = True) -> None:
        super().__init__(shortcut=shortcut)
        self._available = available

    @property
    def name(self) -> str:
        return "Dummy Backend"

    def is_available(self) -> bool:
        return self._available

    def start(self, on_activate: Any) -> bool:
        self.on_activate = on_activate
        self._is_running = True
        return True

    def stop(self) -> None:
        self._is_running = False


def test_base_shortcut_listener_abstract() -> None:
    class IncompleteBackend(BaseShortcutListener):
        @property
        def name(self) -> str:
            return "Incomplete"

        def is_available(self) -> bool:
            return False

        def start(self, on_activate: Any) -> bool:
            return False

        def stop(self) -> None:
            pass

    with pytest.raises(TypeError):
        BaseShortcutListener()  # type: ignore[abstract]


def test_get_backend_candidates_wayland():
    with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}):
        candidates = get_backend_candidates()
        assert candidates[0] is PortalShortcutListener
        assert candidates[1] is PynputShortcutListener
        assert candidates[2] is KeybinderShortcutListener


def test_get_backend_candidates_x11():
    with patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"}):
        candidates = get_backend_candidates()
        assert candidates[0] is KeybinderShortcutListener
        assert candidates[1] is PortalShortcutListener
        assert candidates[2] is PynputShortcutListener


def test_select_best_backend():
    backend = select_best_backend(shortcut="Meta+.")
    assert isinstance(backend, BaseShortcutListener)
    assert backend.shortcut == "Meta+."


def test_portal_shortcut_listener_is_available():
    listener = PortalShortcutListener(shortcut="Meta+.")
    assert listener.name == "XDG Desktop Portal (GlobalShortcuts API)"

    with patch("gi.repository.Gio.bus_get_sync") as mock_bus:
        mock_conn = MagicMock()
        mock_bus.return_value = mock_conn
        with patch("gi.repository.Gio.DBusProxy.new_sync") as mock_proxy_cls:
            mock_proxy = MagicMock()
            mock_proxy.get_name.return_value = "org.freedesktop.portal.Desktop"
            mock_proxy_cls.return_value = mock_proxy

            assert listener.is_available() is True


def test_portal_shortcut_listener_start_and_signal():
    triggered = []

    def callback():
        triggered.append(True)

    listener = PortalShortcutListener(shortcut="Meta+.")

    with patch("gi.repository.Gio.bus_get_sync") as mock_bus:
        mock_conn = MagicMock()
        mock_conn.signal_subscribe.return_value = 123
        mock_bus.return_value = mock_conn

        with patch("gi.repository.Gio.DBusProxy.new_sync") as mock_proxy_cls:
            mock_proxy = MagicMock()
            mock_proxy_cls.return_value = mock_proxy

            with (
                patch.object(
                    listener,
                    "_create_session",
                    return_value="/org/freedesktop/portal/desktop/session/1",
                ),
                patch.object(listener, "_bind_shortcuts", return_value=True),
            ):
                assert listener.start(callback) is True
                assert listener.is_running is True

                # Simulate D-Bus signal callback
                listener._on_portal_signal_activated(
                    mock_conn,
                    "org.freedesktop.portal.Desktop",
                    "/org/freedesktop/portal/desktop",
                    "org.freedesktop.portal.GlobalShortcuts",
                    "Activated",
                    MagicMock(unpack=lambda: ("session_1", "emoji_picker_toggle", 12345, {})),
                )

                assert len(triggered) == 1
                assert triggered[0] is True

                listener.stop()
                assert listener.is_running is False
                mock_conn.signal_unsubscribe.assert_called_with(123)


def test_keybinder_shortcut_listener():
    listener = KeybinderShortcutListener(shortcut="Meta+.")
    assert listener.name == "Keybinder 3.0 (X11 GTK)"
    assert listener._convert_shortcut_format() == "<Super>period"

    triggered = []

    def callback():
        triggered.append(True)

    mock_keybinder = MagicMock()
    mock_keybinder.bind.return_value = True
    listener._keybinder_mod = mock_keybinder

    with patch.object(listener, "is_available", return_value=True):
        assert listener.start(callback) is True
        assert listener.is_running is True

        listener._on_keybinder_triggered("<Super>period", None)
        assert len(triggered) == 1

        listener.stop()
        assert listener.is_running is False
        mock_keybinder.unbind.assert_called_once_with("<Super>period")


def test_pynput_shortcut_listener():
    listener = PynputShortcutListener(shortcut="Meta+.")
    assert listener.name == "pynput GlobalHotKeys (X11)"
    assert listener._convert_shortcut_format() == "<cmd>+."

    with patch.dict("os.environ", {}, clear=True):
        assert listener.is_available() is False

    with patch.dict("os.environ", {"DISPLAY": ":0"}):
        assert listener.is_available() is True

    triggered = []

    def callback():
        triggered.append(True)

    with patch("pynput.keyboard.GlobalHotKeys") as mock_hotkeys_cls:
        mock_hotkey = MagicMock()
        mock_hotkeys_cls.return_value = mock_hotkey

        with patch.dict("os.environ", {"DISPLAY": ":0"}):
            assert listener.start(callback) is True
            assert listener.is_running is True

            listener._on_pynput_triggered()
            assert len(triggered) == 1

            listener.stop()
            assert listener.is_running is False
            mock_hotkey.stop.assert_called_once()


def test_shortcut_daemon_lifecycle():
    triggered = []

    def callback():
        triggered.append(True)

    daemon = ShortcutDaemon(shortcut="Meta+.", on_trigger=callback)
    dummy_backend = DummyBackend(shortcut="Meta+.")

    with patch(
        "gtk_emoji_picker.infrastructure.shortcut_daemon.get_backend_candidates"
    ) as mock_cand:
        mock_cand.return_value = [lambda shortcut: dummy_backend]

        assert daemon.start() is True
        assert daemon.is_running is True
        assert daemon.active_backend is dummy_backend

        dummy_backend.on_activate()
        assert len(triggered) == 1

        daemon.stop()
        assert daemon.is_running is False
        assert daemon.active_backend is None


def test_shortcut_daemon_launch_emoji_picker_prefers_installed_entry_point():
    daemon = ShortcutDaemon(shortcut="Meta+.")

    with patch("shutil.which", return_value="/tmp/gtk-emoji-picker"):
        with patch("subprocess.Popen") as mock_popen:
            daemon.launch_emoji_picker()
            mock_popen.assert_called_once_with(["/tmp/gtk-emoji-picker"])


def test_shortcut_daemon_launch_emoji_picker_falls_back_to_python_module():
    daemon = ShortcutDaemon(shortcut="Meta+.")

    with patch("shutil.which", return_value=None):
        with patch("subprocess.Popen") as mock_popen:
            daemon.launch_emoji_picker()
            mock_popen.assert_called_once_with([sys.executable, "-m", "gtk_emoji_picker"])


def test_shortcut_daemon_trigger_toggles_by_default():
    with patch.object(ShortcutDaemon, "toggle_emoji_picker") as mock_toggle:
        daemon = ShortcutDaemon(shortcut="Meta+.")
        assert daemon.on_trigger is mock_toggle
        daemon.on_trigger()
        mock_toggle.assert_called_once()


def test_shortcut_daemon_toggle_spawns_with_flag():
    daemon = ShortcutDaemon(shortcut="Meta+.")

    with patch("shutil.which", return_value="/tmp/gtk-emoji-picker"):
        with patch("subprocess.Popen") as mock_popen:
            daemon.toggle_emoji_picker()
            mock_popen.assert_called_once_with(["/tmp/gtk-emoji-picker", "--toggle"])

    with patch("shutil.which", return_value=None):
        with patch("subprocess.Popen") as mock_popen:
            daemon.toggle_emoji_picker()
            mock_popen.assert_called_once_with(
                [sys.executable, "-m", "gtk_emoji_picker", "--toggle"]
            )


def test_shortcut_daemon_toggle_error_handled():
    daemon = ShortcutDaemon(shortcut="Meta+.")

    with patch("shutil.which", return_value="/usr/bin/gtk-emoji-picker"):
        with patch("subprocess.Popen", side_effect=Exception("Popen failed")):
            daemon.toggle_emoji_picker()  # should catch exception safely

    with patch("shutil.which", side_effect=Exception("which failed")):
        daemon.toggle_emoji_picker()  # should catch exception safely


def test_hotkey_listener_wrapper():
    hotkey_srv = HotkeyListener(shortcut="Meta+.")
    assert hotkey_srv.shortcut == "Meta+."

    with patch(
        "gtk_emoji_picker.infrastructure.shortcut_daemon.ShortcutDaemon.start",
        return_value=True,
    ):
        hotkey_srv.start()
        assert hotkey_srv.daemon is not None

        with patch.object(hotkey_srv, "launch_emoji_picker") as mock_launch:
            hotkey_srv.on_shortcut_activated()
            mock_launch.assert_called_once()

        hotkey_srv.stop()
        assert hotkey_srv.daemon is None


def test_portal_shortcut_listener_error_paths():
    listener = PortalShortcutListener(shortcut="Meta+.")

    # is_available failure when bus_get_sync raises exception
    with patch("gi.repository.Gio.bus_get_sync", side_effect=Exception("D-Bus Error")):
        assert listener.is_available() is False

    # start failure when dbus_conn is None
    with patch("gi.repository.Gio.bus_get_sync", return_value=None):
        assert listener.start(lambda: None) is False
        assert listener.is_running is False

    # start failure when exception occurs
    with patch("gi.repository.Gio.bus_get_sync", side_effect=Exception("Conn fail")):
        assert listener.start(lambda: None) is False

    # signal activation exception handling
    mock_conn = MagicMock()
    listener._on_portal_signal_activated(
        mock_conn,
        "sender",
        "/path",
        "iface",
        "sig",
        MagicMock(unpack=side_effect_unpack)
        if (side_effect_unpack := MagicMock(side_effect=Exception("unpack error")))
        else None,
    )


def test_keybinder_shortcut_listener_error_paths():
    listener = KeybinderShortcutListener(shortcut="Meta+.")

    # is_available failure
    with patch("builtins.__import__", side_effect=ImportError("No keybinder")):
        assert listener.is_available() is False

    # start failure when not available
    with patch.object(listener, "is_available", return_value=False):
        assert listener.start(lambda: None) is False

    # start failure when keybinder.bind returns False
    mock_kb = MagicMock()
    mock_kb.bind.return_value = False
    listener._keybinder_mod = mock_kb
    with patch.object(listener, "is_available", return_value=True):
        assert listener.start(lambda: None) is False

    # start failure when exception thrown
    mock_kb_err = MagicMock()
    mock_kb_err.bind.side_effect = Exception("Bind err")
    listener._keybinder_mod = mock_kb_err
    with patch.object(listener, "is_available", return_value=True):
        assert listener.start(lambda: None) is False

    # stop exception handling
    mock_kb_stop_err = MagicMock()
    mock_kb_stop_err.unbind.side_effect = Exception("Unbind err")
    listener._keybinder_mod = mock_kb_stop_err
    listener._bound_accel = "<Super>period"
    listener.stop()  # Should handle exception without raising
    assert listener._bound_accel is None


def test_pynput_shortcut_listener_error_paths():
    listener = PynputShortcutListener(shortcut="CustomKey")
    assert listener._convert_shortcut_format() == "CustomKey"

    # is_available exception
    with patch.dict("os.environ", {"DISPLAY": ":0"}):
        with patch("builtins.__import__", side_effect=ImportError("No pynput")):
            assert listener.is_available() is False

    # start failure when not available
    with patch.object(listener, "is_available", return_value=False):
        assert listener.start(lambda: None) is False

    # start failure when exception thrown during listener init
    with patch.object(listener, "is_available", return_value=True):
        with patch("pynput.keyboard.GlobalHotKeys", side_effect=Exception("Init error")):
            assert listener.start(lambda: None) is False

    # stop exception handling
    mock_pynput_listener = MagicMock()
    mock_pynput_listener.stop.side_effect = Exception("Stop error")
    listener._listener = mock_pynput_listener
    listener.stop()  # Should handle exception gracefully
    assert listener._listener is None


def test_shortcut_daemon_start_and_launch_failures(tmp_path):
    daemon = ShortcutDaemon()

    # start failure when all candidates and fallback fail
    with patch(
        "gtk_emoji_picker.infrastructure.shortcut_daemon.get_backend_candidates", return_value=[]
    ):
        with patch(
            "gtk_emoji_picker.infrastructure.shortcut_daemon.select_best_backend", return_value=None
        ):
            assert daemon.start() is False

    # launch_emoji_picker fallback when shutil.which returns None
    with patch("shutil.which", return_value=None):
        with patch("subprocess.Popen") as mock_popen:
            daemon.launch_emoji_picker()
            mock_popen.assert_called_once_with([sys.executable, "-m", "gtk_emoji_picker"])

    # launch_emoji_picker when executable binary exists
    with patch("shutil.which", return_value="/usr/bin/gtk-emoji-picker"):
        with patch("subprocess.Popen") as mock_popen:
            daemon.launch_emoji_picker()
            mock_popen.assert_called_once_with(["/usr/bin/gtk-emoji-picker"])

    # launch_emoji_picker Popen exception handled gracefully
    with patch("subprocess.Popen", side_effect=Exception("Popen failed")):
        daemon.launch_emoji_picker()  # should catch exception safely


def test_shortcut_daemon_run_and_signals():
    daemon = ShortcutDaemon()

    # run returns 1 on start failure
    with patch.object(daemon, "start", return_value=False):
        assert daemon.run() == 1

    # run success and signal handling
    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True

    with patch.object(daemon, "start", return_value=True):
        with patch("gi.repository.GLib.MainLoop", return_value=mock_loop):
            with patch("signal.signal") as mock_signal:
                mock_loop.run.side_effect = KeyboardInterrupt()
                assert daemon.run() == 0
                assert mock_signal.call_count == 2


def test_hotkey_listener_fallback_and_errors(tmp_path):
    hotkey_srv = HotkeyListener(shortcut="Meta+.")

    # Daemon start returns False -> triggers _fallback_pynput
    with patch(
        "gtk_emoji_picker.infrastructure.shortcut_daemon.ShortcutDaemon.start", return_value=False
    ):
        with patch.object(hotkey_srv, "_fallback_pynput") as mock_fb:
            hotkey_srv.start()
            mock_fb.assert_called_once()

    # Exception during start triggers sys.exit(1)
    with patch(
        "gtk_emoji_picker.infrastructure.shortcut_daemon.ShortcutDaemon.start",
        side_effect=Exception("Fatal start error"),
    ):
        with patch("sys.exit") as mock_exit:
            hotkey_srv.start()
            mock_exit.assert_called_once_with(1)

    # launch_emoji_picker with missing script
    hotkey_srv.picker_app = None
    with patch("os.path.isfile", return_value=False):
        hotkey_srv.launch_emoji_picker()

    # launch_emoji_picker with non-executable script
    dummy_file = tmp_path / "emoji_picker.py"
    dummy_file.write_text("print(1)")
    dummy_file.chmod(0o644)
    with patch("os.path.abspath", return_value=str(tmp_path / "hotkey_service.py")):
        with patch("os.path.isfile", return_value=True):
            with patch("os.access", return_value=False):
                with patch("os.chmod") as mock_chmod:
                    with patch("subprocess.Popen"):
                        hotkey_srv.launch_emoji_picker()
                        mock_chmod.assert_called_once()

    # launch_emoji_picker Popen exception
    with patch("os.path.isfile", return_value=True):
        with patch("os.access", return_value=True):
            with patch("subprocess.Popen", side_effect=Exception("Popen fail")):
                hotkey_srv.launch_emoji_picker()

    # stop with listener object
    mock_listener = MagicMock()
    hotkey_srv.daemon = None
    hotkey_srv.listener = mock_listener
    hotkey_srv.stop()
    mock_listener.stop.assert_called_once()
    assert hotkey_srv.listener is None


def test_hotkey_service_main_execution():
    from hotkey_service import main

    # Daemon path in main
    mock_daemon = MagicMock()
    with patch("hotkey_service.HotkeyListener") as mock_listener_cls:
        mock_srv = MagicMock()
        mock_srv.daemon = mock_daemon
        mock_listener_cls.return_value = mock_srv

        with patch("signal.signal") as mock_signal:
            assert main() == 0
            mock_daemon.run.assert_called_once()

            # Execute signal handler
            sig_handler = mock_signal.call_args_list[0][0][1]
            with patch("sys.exit") as mock_exit:
                sig_handler(15, None)
                mock_srv.stop.assert_called()
                mock_exit.assert_called_once_with(0)

    # Listener join path and KeyboardInterrupt in main
    mock_thread_listener = MagicMock()
    with patch("hotkey_service.HotkeyListener") as mock_listener_cls:
        mock_srv = MagicMock()
        mock_srv.daemon = None
        mock_srv.listener = mock_thread_listener
        mock_thread_listener.join.side_effect = KeyboardInterrupt()
        mock_listener_cls.return_value = mock_srv

        assert main() == 0
        mock_srv.stop.assert_called()


def test_portal_shortcut_listener_create_session_and_bind_shortcuts():
    listener = PortalShortcutListener(shortcut="Meta+.")
    mock_conn = MagicMock()
    mock_conn.get_unique_name.return_value = ":1.100"
    mock_proxy = MagicMock()
    listener._dbus_conn = mock_conn
    listener._proxy = mock_proxy

    # Test _preferred_trigger
    assert listener._preferred_trigger() == "Super+period"
    listener_custom = PortalShortcutListener(shortcut="Ctrl+Alt+E")
    assert listener_custom._preferred_trigger() == "Ctrl+Alt+E"

    # Test _make_token & _request_path_for_token
    token = listener._make_token("test")
    assert token.startswith("test_")
    req_path = listener._request_path_for_token(token)
    assert req_path == f"/org/freedesktop/portal/desktop/request/1_100/{token}"

    # Test _quit_loop_if_running
    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    assert PortalShortcutListener._quit_loop_if_running(mock_loop) is False
    mock_loop.quit.assert_called_once()

    # Test _create_session success path
    mock_proxy.call_sync.return_value = MagicMock(unpack=lambda: (req_path,))

    def fake_subscribe(request_path, callback):
        callback(0, {"session_handle": "/org/freedesktop/portal/desktop/session/s1"})
        return 999

    with patch.object(listener, "_subscribe_to_request_response", side_effect=fake_subscribe):
        with patch("gi.repository.GLib.MainLoop") as mock_mainloop_cls:
            mock_loop_instance = MagicMock()
            mock_loop_instance.is_running.return_value = False
            mock_mainloop_cls.return_value = mock_loop_instance
            with patch("gi.repository.GLib.timeout_add", return_value=123):
                with patch("gi.repository.GLib.source_remove") as mock_src_rem:
                    session_h = listener._create_session()
                    assert session_h == "/org/freedesktop/portal/desktop/session/s1"
                    mock_src_rem.assert_called_once_with(123)

    # Test _bind_shortcuts
    mock_proxy.call_sync.return_value = MagicMock(unpack=lambda: (req_path,))
    with patch.object(listener, "_subscribe_to_request_response") as mock_sub:
        listener._bind_shortcuts("/org/freedesktop/portal/desktop/session/s1")
        mock_sub.assert_called_once()

    # Test _on_session_closed
    with patch.object(listener, "stop") as mock_stop:
        listener._on_session_closed(mock_conn, "sender", "/path", "iface", "sig", None)
        mock_stop.assert_called_once()


def test_portal_shortcut_listener_full_stop_cleanup():
    listener = PortalShortcutListener(shortcut="Meta+.")
    mock_conn = MagicMock()
    listener._dbus_conn = mock_conn
    listener._session_handle = "/session/1"
    listener._signal_sub_id = 10
    listener._session_closed_sub_id = 20
    listener._request_signal_sub_ids = [30, 40]

    with patch("gi.repository.Gio.DBusProxy.new_sync") as mock_proxy_cls:
        mock_session_proxy = MagicMock()
        mock_proxy_cls.return_value = mock_session_proxy
        listener.stop()

        mock_session_proxy.call_sync.assert_called_once_with(
            "Close", None, Gio.DBusCallFlags.NONE, 1000, None
        )
        assert mock_conn.signal_unsubscribe.call_count == 4
        assert listener._is_running is False
        assert listener._dbus_conn is None
        assert listener._session_handle is None
