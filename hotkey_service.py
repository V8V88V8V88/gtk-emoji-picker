#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import os
os.environ['GDK_BACKEND'] = 'x11'  # Force X11 for this application only

from Xlib import X, XK, display
from Xlib.ext import record
from Xlib.protocol import rq
import threading
import subprocess
import sys
import signal
import logging

logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')

class HotkeyService:
    def __init__(self):
        try:
            self.local_display = display.Display()
            self.record_display = display.Display()
            self.context = None
            self.keymap = {}
            self.meta_pressed = False
            
            # Initialize keymap
            for name in dir(XK):
                if name.startswith("XK_"):
                    self.keymap[getattr(XK, name)] = name[3:]
            
            logging.info("HotkeyService initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize displays: {e}")
            sys.exit(1)

    def print_key(self, keycode):
        keysym = self.local_display.keycode_to_keysym(keycode, 0)
        if keysym in self.keymap:
            logging.debug(f"Key pressed: {self.keymap[keysym]}")
        return keysym

    def handler(self, reply):
        if reply.category != record.FromServer:
            return
        if reply.client_swapped:
            return

        data = reply.data
        while len(data):
            event, data = rq.EventField(None).parse_binary_value(
                data, self.record_display.display, None, None)

            if event.type == X.KeyPress:
                keysym = self.print_key(event.detail)
                if keysym in (XK.XK_Super_L, XK.XK_Super_R):
                    self.meta_pressed = True
                    logging.debug("Meta key pressed")
            elif event.type == X.KeyRelease:
                keysym = self.print_key(event.detail)
                if keysym in (XK.XK_Super_L, XK.XK_Super_R):
                    self.meta_pressed = False
                    logging.debug("Meta key released")
                elif keysym == XK.XK_period and self.meta_pressed:
                    logging.info("Hotkey combination detected (Meta + .)")
                    self.launch_emoji_picker()

    def launch_emoji_picker(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            emoji_picker_path = os.path.join(script_dir, 'emoji_picker.py')
            
            # Launch emoji picker with X11 backend
            env = os.environ.copy()
            env['GDK_BACKEND'] = 'x11'
            
            logging.info(f"Launching emoji picker from: {emoji_picker_path}")
            subprocess.Popen([emoji_picker_path], env=env)
        except Exception as e:
            logging.error(f"Failed to launch emoji picker: {e}")

    def setup_record_context(self):
        try:
            self.context = self.record_display.record_create_context(
                0,
                [record.AllClients],
                [{
                    'core_requests': (0, 0),
                    'core_replies': (0, 0),
                    'ext_requests': (0, 0, 0, 0),
                    'ext_replies': (0, 0, 0, 0),
                    'delivered_events': (0, 0),
                    'device_events': (X.KeyPress, X.KeyRelease),
                    'errors': (0, 0),
                    'client_started': False,
                    'client_died': False,
                }]
            )
            logging.info("Record context created successfully")
        except Exception as e:
            logging.error(f"Failed to create record context: {e}")
            sys.exit(1)

    def start(self):
        logging.info("Starting hotkey service...")
        self.setup_record_context()
        
        def signal_handler(signum, frame):
            logging.info("Received signal to terminate")
            if self.context:
                self.record_display.record_free_context(self.context)
            self.local_display.close()
            self.record_display.close()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            self.record_display.record_enable_context(self.context, self.handler)
        except Exception as e:
            logging.error(f"Failed to enable record context: {e}")
            self.record_display.record_free_context(self.context)
            sys.exit(1)

def main():
    service = HotkeyService()
    service.start()

if __name__ == '__main__':
    main()