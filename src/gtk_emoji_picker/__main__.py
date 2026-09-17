"""Main application entry point for python -m gtk_emoji_picker."""

import sys


def main() -> int:
    from emoji_picker import main as picker_main

    res = picker_main()
    return int(res) if res is not None else 0


if __name__ == "__main__":
    sys.exit(main())
