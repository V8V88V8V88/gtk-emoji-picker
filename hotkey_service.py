#!/usr/bin/env python3
import os
os.environ['GDK_BACKEND'] = 'x11'

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gtk, Gdk, Gio, GLib
import subprocess
import signal
import sys
import logging

logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(levelname)s - %(message)s')

class HotkeyListener(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.example.emojipicker.hotkey',
                        flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        
    def do_activate(self):
        # Create an invisible window to capture global hotkeys
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_default_size(1, 1)
        
        # Make the window invisible but keep it running
        self.window.set_opacity(0)
        self.window.set_decorated(False)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        
        # Create a controller for key events
        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', self.on_key_pressed)
        self.window.add_controller(key_controller)
        
        # Setup global keyboard shortcut
        self.setup_global_shortcut()
        
        self.window.present()
        logging.info("Hotkey listener started")

    def setup_global_shortcut(self):
        action = Gio.SimpleAction.new('open-emoji-picker', None)
        action.connect('activate', self.on_shortcut_activated)
        self.add_action(action)
        
        # Set up the keyboard shortcut (Super/Meta + period)
        self.set_accels_for_action('app.open-emoji-picker', ['<Super>period'])
        logging.info("Global shortcut registered: Super + period")

    def on_shortcut_activated(self, action, parameter):
        logging.info("Shortcut activated!")
        self.launch_emoji_picker()

    def on_key_pressed(self, controller, keyval, keycode, state):
        logging.debug(f"Key pressed - keyval: {keyval}, keycode: {keycode}, state: {state}")
        
        # Check if Super/Meta is being held (state & Gdk.ModifierType.SUPER_MASK)
        is_super = bool(state & Gdk.ModifierType.SUPER_MASK)
        is_period = keyval == Gdk.KEY_period
        
        if is_super and is_period:
            logging.info("Hotkey combination detected: Super + period")
            self.launch_emoji_picker()
            return True
        return False

    def launch_emoji_picker(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            emoji_picker_path = os.path.join(script_dir, 'emoji_picker.py')
            
            env = os.environ.copy()
            env['GDK_BACKEND'] = 'x11'
            
            logging.info(f"Launching emoji picker from: {emoji_picker_path}")
            subprocess.Popen([emoji_picker_path], env=env)
        except Exception as e:
            logging.error(f"Failed to launch emoji picker: {e}", exc_info=True)

def main():
    def signal_handler(signum, frame):
        logging.info("Received signal to terminate")
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    app = HotkeyListener()
    return app.run(None)

if __name__ == '__main__':
    main()