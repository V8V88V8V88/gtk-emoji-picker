#!/usr/bin/env python3
import os
import sys
import subprocess
import signal
import logging
from pynput import keyboard

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class HotkeyListener:
    def __init__(self):
        self.listener = None

    def start(self):
        # Start listening for global hotkeys
        self.listener = keyboard.GlobalHotKeys({
            '<cmd>+.' : self.on_shortcut_activated,  # Meta/Super + .
        })
        self.listener.start()
        logging.info("Global hotkey listener started")

    def on_shortcut_activated(self):
        logging.info("Shortcut activated!")
        self.launch_emoji_picker()

    def launch_emoji_picker(self):
        try:
            # Get the path to the emoji picker script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            emoji_picker_path = os.path.join(script_dir, 'emoji_picker.py')
            
            # Check if the emoji picker script exists
            if not os.path.isfile(emoji_picker_path):
                logging.error(f"Emoji picker not found at: {emoji_picker_path}")
                return
                
            # Ensure the script is executable
            if not os.access(emoji_picker_path, os.X_OK):
                logging.info("Setting executable permission on emoji picker")
                os.chmod(emoji_picker_path, 0o755)
            
            # Launch the emoji picker
            logging.info(f"Launching emoji picker from: {emoji_picker_path}")
            subprocess.Popen([sys.executable, emoji_picker_path])
        except Exception as e:
            logging.error(f"Failed to launch emoji picker: {e}", exc_info=True)

def main():
    # Handle termination signals gracefully
    def signal_handler(signum, frame):
        logging.info("Received signal to terminate")
        if app.listener:
            app.listener.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize and start the hotkey listener
    app = HotkeyListener()
    app.start()

    # Keep the script running
    try:
        while True:
            pass  # Infinite loop to keep the script alive
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt to terminate")
        if app.listener:
            app.listener.stop()

if __name__ == '__main__':
    main()