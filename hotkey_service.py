#!/usr/bin/env python3
from Xlib import X, display
from Xlib.ext import record
from Xlib.protocol import rq
import threading
import subprocess
import os

class HotkeyService:
    def __init__(self):
        self.display = display.Display()
        self.root = self.display.screen().root
        self.ctx = None
        self.meta_pressed = False
        
    def handler(self, reply):
        if reply.category != record.FromServer:
            return
        
        if reply.client_swapped:
            return
            
        data = reply.data
        while len(data):
            event, data = rq.EventField(None).parse_binary_value(
                data, self.display.display, None, None)
            
            if event.type == X.KeyPress:
                keysym = self.display.keycode_to_keysym(event.detail, 0)
                if keysym == 0xffe7:  # Meta key
                    self.meta_pressed = True
            elif event.type == X.KeyRelease:
                keysym = self.display.keycode_to_keysym(event.detail, 0)
                if keysym == 0xffe7:  # Meta key
                    self.meta_pressed = False
                elif keysym == 0x2e and self.meta_pressed:  # Period key
                    self.launch_emoji_picker()
    
    def launch_emoji_picker(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen([os.path.join(script_dir, 'emoji_picker.py')])
    
    def start(self):
        ctx = self.display.record_create_context(
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
        
        self.display.record_enable_context(ctx, self.handler)
        self.display.record_free_context(ctx)

def main():
    service = HotkeyService()
    service.start()

if __name__ == '__main__':
    main()
