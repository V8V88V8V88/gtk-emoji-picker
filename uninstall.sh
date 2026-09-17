#!/usr/bin/env bash
# Wrapper script for uninstalling GTK Emoji Picker
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/install.sh" --uninstall "$@"
