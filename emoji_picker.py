#!/usr/bin/env python3
import os
os.environ['GDK_BACKEND'] = 'x11'  # Force X11 for this application only

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gio, Gdk
import json
import logging

logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')

class EmojiPicker(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.v8v88v8v88.emojipicker',
                        flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.search_entry = None
        self.emoji_list = None
        self.load_emojis()
        
    def load_emojis(self):
        try:
            emoji_file = os.path.join(os.path.dirname(__file__), 'emojis.json')
            with open(emoji_file, 'r', encoding='utf-8') as f:
                self.emojis = json.load(f)
            logging.info("Emojis loaded successfully")
        except Exception as e:
            logging.error(f"Failed to load emojis: {e}")
            self.emojis = []
    
    def do_activate(self):
        if not self.window:
            self.window = Gtk.ApplicationWindow(application=self)
            self.window.set_title("Emoji Picker")
            self.window.set_default_size(400, 500)
            
            # Main box
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            self.window.set_child(box)
            
            # Search entry
            self.search_entry = Gtk.SearchEntry()
            self.search_entry.connect('search-changed', self.on_search_changed)
            box.append(self.search_entry)
            
            # Scrolled window for emoji list
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_vexpand(True)
            box.append(scrolled)
            
            # Emoji list
            self.emoji_list = Gtk.ListBox()
            self.emoji_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self.emoji_list.connect('row-activated', self.on_emoji_selected)
            scrolled.set_child(self.emoji_list)
            
            self.populate_emoji_list()
            
        self.window.present()
    
    def populate_emoji_list(self, filter_text=None):
        # Clear existing items
        while True:
            row = self.emoji_list.get_first_child()
            if row:
                self.emoji_list.remove(row)
            else:
                break
        
        # Add filtered emojis
        for emoji in self.emojis:
            if filter_text and filter_text.lower() not in emoji['name'].lower():
                continue
            
            label = Gtk.Label(label=f"{emoji['emoji']} {emoji['name']}")
            label.set_halign(Gtk.Align.START)
            self.emoji_list.append(label)
    
    def on_search_changed(self, entry):
        self.populate_emoji_list(entry.get_text())
    
    def on_emoji_selected(self, list_box, row):
        try:
            emoji = self.emojis[row.get_index()]['emoji']
            clipboard = Gdk.Display.get_default().get_clipboard()
            clipboard.set_text(emoji)
            logging.info(f"Copied emoji to clipboard: {emoji}")
            self.window.close()
        except Exception as e:
            logging.error(f"Failed to copy emoji to clipboard: {e}")

def main():
    app = EmojiPicker()
    return app.run(None)

if __name__ == '__main__':
    main()