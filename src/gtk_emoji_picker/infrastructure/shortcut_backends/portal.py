"""XDG Desktop Portal GlobalShortcuts backend for Wayland/X11."""

import logging
import secrets
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib

from gtk_emoji_picker.infrastructure.shortcut_backends.base import BaseShortcutListener

logger = logging.getLogger(__name__)


class PortalShortcutListener(BaseShortcutListener):
    """Global shortcut listener implementation using XDG Desktop Portal."""

    BUS_NAME = "org.freedesktop.portal.Desktop"
    OBJECT_PATH = "/org/freedesktop/portal/desktop"
    INTERFACE_NAME = "org.freedesktop.portal.GlobalShortcuts"
    REQUEST_INTERFACE = "org.freedesktop.portal.Request"
    SESSION_INTERFACE = "org.freedesktop.portal.Session"
    SHORTCUT_ID = "emoji_picker_toggle"

    def __init__(self, shortcut: str = "Meta+.") -> None:
        super().__init__(shortcut=shortcut)
        self._dbus_conn: Gio.DBusConnection | None = None
        self._proxy: Gio.DBusProxy | None = None
        self._signal_sub_id: int | None = None
        self._session_closed_sub_id: int | None = None
        self._request_signal_sub_ids: list[int] = []
        self._session_handle: str | None = None

    @property
    def name(self) -> str:
        return "XDG Desktop Portal (GlobalShortcuts API)"

    def is_available(self) -> bool:
        """Check if the portal interface is reachable on the session bus."""
        try:
            conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            if not conn:
                return False

            proxy = Gio.DBusProxy.new_sync(
                conn,
                Gio.DBusProxyFlags.NONE,
                None,
                self.BUS_NAME,
                self.OBJECT_PATH,
                self.INTERFACE_NAME,
                None,
            )
            if proxy is None or proxy.get_name() != self.BUS_NAME:
                return False

            version = proxy.get_cached_property("version")
            return version is None or int(version.unpack()) >= 1
        except Exception as exc:
            logger.debug("Portal backend unavailable: %s", exc)
            return False

    def start(self, on_activate: Callable[[], None]) -> bool:
        """Initialize D-Bus session and register the portal shortcut."""
        self.on_activate = on_activate

        try:
            self._dbus_conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            if not self._dbus_conn:
                logger.error("Failed to connect to D-Bus session bus.")
                return False

            self._proxy = Gio.DBusProxy.new_sync(
                self._dbus_conn,
                Gio.DBusProxyFlags.NONE,
                None,
                self.BUS_NAME,
                self.OBJECT_PATH,
                self.INTERFACE_NAME,
                None,
            )
            self._signal_sub_id = self._dbus_conn.signal_subscribe(
                self.BUS_NAME,
                self.INTERFACE_NAME,
                "Activated",
                self.OBJECT_PATH,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_portal_signal_activated,
            )

            self._session_handle = self._create_session()
            if not self._session_handle:
                logger.error("Portal session creation did not return a session handle.")
                self.stop()
                return False

            self._session_closed_sub_id = self._dbus_conn.signal_subscribe(
                self.BUS_NAME,
                self.SESSION_INTERFACE,
                "Closed",
                self._session_handle,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_session_closed,
            )
            self._bind_shortcuts(self._session_handle)
            self._is_running = True
            logger.info("Portal shortcut listener started for '%s'", self.shortcut)
            return True
        except Exception as exc:
            logger.error("Failed to start PortalShortcutListener: %s", exc, exc_info=True)
            self.stop()
            return False

    def _make_token(self, prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(8)}"

    def _request_path_for_token(self, token: str) -> str:
        if not self._dbus_conn:
            raise RuntimeError("D-Bus connection is not initialized")

        unique_name = self._dbus_conn.get_unique_name()
        if not unique_name:
            raise RuntimeError("D-Bus unique name is unavailable")

        sender = unique_name.lstrip(":").replace(".", "_")
        return f"{self.OBJECT_PATH}/request/{sender}/{token}"

    def _subscribe_to_request_response(
        self,
        request_path: str,
        callback: Callable[[int, dict[str, Any]], None],
    ) -> int:
        if not self._dbus_conn:
            raise RuntimeError("D-Bus connection is not initialized")

        def _handle_response(
            connection: Gio.DBusConnection,
            sender_name: str,
            object_path: str,
            interface_name: str,
            signal_name: str,
            parameters: GLib.Variant,
        ) -> None:
            response, results = parameters.unpack()
            callback(int(response), dict(results))

        sub_id = self._dbus_conn.signal_subscribe(
            self.BUS_NAME,
            self.REQUEST_INTERFACE,
            "Response",
            request_path,
            None,
            Gio.DBusSignalFlags.NONE,
            _handle_response,
        )
        self._request_signal_sub_ids.append(int(sub_id))
        return int(sub_id)

    def _unsubscribe_request_signal(self, sub_id: int) -> None:
        if self._dbus_conn:
            self._dbus_conn.signal_unsubscribe(sub_id)
        if sub_id in self._request_signal_sub_ids:
            self._request_signal_sub_ids.remove(sub_id)

    def _create_session(self) -> str | None:
        if not self._proxy:
            return None

        handle_token = self._make_token("create")
        session_token = self._make_token("session")
        request_path = self._request_path_for_token(handle_token)
        response_payload: dict[str, Any] = {}
        loop = GLib.MainLoop()

        def _on_response(response: int, results: dict[str, Any]) -> None:
            response_payload["response"] = response
            response_payload["results"] = results
            if loop.is_running():
                loop.quit()

        sub_id = self._subscribe_to_request_response(request_path, _on_response)
        returned_path = self._proxy.call_sync(
            "CreateSession",
            GLib.Variant(
                "(a{sv})",
                (
                    {
                        "handle_token": GLib.Variant("s", handle_token),
                        "session_handle_token": GLib.Variant("s", session_token),
                    },
                ),
            ),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        ).unpack()[0]
        if returned_path != request_path:
            self._unsubscribe_request_signal(sub_id)
            sub_id = self._subscribe_to_request_response(returned_path, _on_response)

        timeout_id = GLib.timeout_add(5000, self._quit_loop_if_running, loop)
        try:
            loop.run()
        finally:
            GLib.source_remove(timeout_id)
            self._unsubscribe_request_signal(sub_id)

        if response_payload.get("response") != 0:
            logger.error(
                "Portal CreateSession failed with response code %s",
                response_payload.get("response"),
            )
            return None

        results = response_payload.get("results", {})
        session_handle = results.get("session_handle")
        return str(session_handle) if session_handle else None

    def _preferred_trigger(self) -> str:
        if self.shortcut in {"Meta+.", "Super+."}:
            return "Super+period"
        return self.shortcut

    def _bind_shortcuts(self, session_handle: str) -> None:
        if not self._proxy:
            return

        handle_token = self._make_token("bind")
        request_path = self._request_path_for_token(handle_token)

        def _on_bind_response(response: int, results: dict[str, Any]) -> None:
            if response != 0:
                logger.error("Portal BindShortcuts failed with response code %s", response)
                self._is_running = False
                return

            logger.info("Portal shortcut binding confirmed: %s", results.get("shortcuts", []))

        self._subscribe_to_request_response(request_path, _on_bind_response)
        returned_path = self._proxy.call_sync(
            "BindShortcuts",
            GLib.Variant(
                "(oa(sa{sv})sa{sv})",
                (
                    session_handle,
                    [
                        (
                            self.SHORTCUT_ID,
                            {
                                "description": GLib.Variant("s", "Toggle GTK Emoji Picker"),
                                "preferred_trigger": GLib.Variant("s", self._preferred_trigger()),
                            },
                        )
                    ],
                    "",
                    {"handle_token": GLib.Variant("s", handle_token)},
                ),
            ),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        ).unpack()[0]
        if returned_path != request_path:
            logger.debug("Portal returned unexpected bind request path: %s", returned_path)

    def _on_portal_signal_activated(
        self,
        connection: Gio.DBusConnection,
        sender_name: str,
        object_path: str,
        interface_name: str,
        signal_name: str,
        parameters: GLib.Variant,
    ) -> None:
        """Handle Activated D-Bus signals from the portal."""
        try:
            shortcut_id = ""
            if parameters:
                unpacked = parameters.unpack()
                if isinstance(unpacked, (tuple, list)) and len(unpacked) > 1:
                    shortcut_id = str(unpacked[1])
                logger.info("Portal shortcut activated: %s", shortcut_id)

            if shortcut_id == self.SHORTCUT_ID and self.on_activate:
                self.on_activate()
        except Exception as exc:
            logger.error("Error handling portal signal: %s", exc, exc_info=True)

    def _on_session_closed(
        self,
        connection: Gio.DBusConnection,
        sender_name: str,
        object_path: str,
        interface_name: str,
        signal_name: str,
        parameters: GLib.Variant,
    ) -> None:
        logger.warning("Portal shortcut session was closed by the desktop portal")
        self.stop()

    @staticmethod
    def _quit_loop_if_running(loop: GLib.MainLoop) -> bool:
        if loop.is_running():
            loop.quit()
        return False

    def stop(self) -> None:
        """Disconnect D-Bus signal subscriptions and clean up."""
        if self._dbus_conn and self._session_handle:
            try:
                session_proxy = Gio.DBusProxy.new_sync(
                    self._dbus_conn,
                    Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
                    None,
                    self.BUS_NAME,
                    self._session_handle,
                    self.SESSION_INTERFACE,
                    None,
                )
                session_proxy.call_sync("Close", None, Gio.DBusCallFlags.NONE, 1000, None)
            except Exception:
                pass

        if self._dbus_conn and self._signal_sub_id:
            try:
                self._dbus_conn.signal_unsubscribe(self._signal_sub_id)
            except Exception:
                pass
            self._signal_sub_id = None

        if self._dbus_conn and self._session_closed_sub_id:
            try:
                self._dbus_conn.signal_unsubscribe(self._session_closed_sub_id)
            except Exception:
                pass
            self._session_closed_sub_id = None

        if self._dbus_conn:
            for sub_id in list(self._request_signal_sub_ids):
                try:
                    self._dbus_conn.signal_unsubscribe(sub_id)
                except Exception:
                    pass
                finally:
                    self._request_signal_sub_ids.remove(sub_id)

        self._dbus_conn = None
        self._proxy = None
        self._session_handle = None
        self._is_running = False
        logger.info("Portal shortcut listener stopped.")
