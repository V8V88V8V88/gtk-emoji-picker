# GTK Emoji Picker

A simple GTK4-based emoji picker that can be triggered globally using Meta + . shortcut.

## Prerequisites

- Python 3.x
- GTK 4
- Python-GObject
- Python-Xlib

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd gtk-emoji-picker
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Make scripts executable:
```bash
chmod +x emoji_picker.py hotkey_service.py
```

5. Update the desktop entry:
Edit ~/.config/autostart/emoji-picker-hotkey.desktop and update the Exec path.

## Usage

1. Start the hotkey service:
```bash
./hotkey_service.py
```

2. Press Meta + . to open the emoji picker
3. Search for emojis using the search bar
4. Click on an emoji to copy it to clipboard

## License

MIT License
