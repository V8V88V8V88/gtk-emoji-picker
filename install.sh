#!/usr/bin/env bash
# ==============================================================================
# GTK Emoji Picker - Installation & Distribution Script
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="user"
PREFIX=""
ENABLE_SERVICE=false
UNINSTALL=false
DRY_RUN=false
SERVICE_NAME="gtk-emoji-picker-daemon.service"

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --user              Install for current user (~/.local) [Default]
  --system            Install system-wide (/usr/local, requires root)
  --prefix=PATH       Set custom installation prefix directory
  --enable-service    Automatically enable and start systemd user autostart service
  --uninstall         Remove installed application files and systemd service
  --dry-run           Show planned actions without making changes
  -h, --help          Show this help message and exit
EOF
}

for arg in "$@"; do
    case $arg in
        --user)
            MODE="user"
            ;;
        --system)
            MODE="system"
            ;;
        --prefix=*)
            PREFIX="${arg#*=}"
            MODE="custom"
            ;;
        --enable-service)
            ENABLE_SERVICE=true
            ;;
        --uninstall)
            UNINSTALL=true
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$arg'" >&2
            show_help
            exit 1
            ;;
    esac
done

if [ "$MODE" = "system" ] && [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "Error: --system installation requires root privileges." >&2
    exit 1
fi

# Determine installation locations
if [ -n "$PREFIX" ]; then
    BIN_DIR="$PREFIX/bin"
    APP_DIR="$PREFIX/share/applications"
    SYSTEMD_DIR="$PREFIX/lib/systemd/user"
elif [ "$MODE" = "system" ]; then
    PREFIX="/usr/local"
    BIN_DIR="/usr/local/bin"
    APP_DIR="/usr/local/share/applications"
    SYSTEMD_DIR="/usr/local/lib/systemd/user"
else
    PREFIX="$HOME/.local"
    BIN_DIR="$HOME/.local/bin"
    APP_DIR="$HOME/.local/share/applications"
    SYSTEMD_DIR="$HOME/.config/systemd/user"
fi

DESKTOP_FILE_SRC="$SCRIPT_DIR/data/gtk-emoji-picker.desktop"
if [ ! -f "$DESKTOP_FILE_SRC" ]; then
    DESKTOP_FILE_SRC="$SCRIPT_DIR/gtk-emoji-picker.desktop"
fi

SERVICE_FILE_SRC="$SCRIPT_DIR/data/gtk-emoji-picker-daemon.service"
if [ ! -f "$SERVICE_FILE_SRC" ]; then
    SERVICE_FILE_SRC="$SCRIPT_DIR/gtk-emoji-picker-daemon.service"
fi

if [ "$UNINSTALL" = true ]; then
    echo "=== Uninstalling GTK Emoji Picker ==="
    
    if command -v systemctl >/dev/null 2>&1; then
        if [ "$DRY_RUN" = true ]; then
            echo "[Dry Run] systemctl --user disable --now $SERVICE_NAME"
        else
            systemctl --user disable --now "$SERVICE_NAME" >/dev/null 2>&1 || true
        fi
    fi

    TARGET_SERVICE="$SYSTEMD_DIR/$SERVICE_NAME"
    TARGET_DESKTOP="$APP_DIR/gtk-emoji-picker.desktop"

    if [ "$DRY_RUN" = true ]; then
        echo "[Dry Run] Remove service unit: $TARGET_SERVICE"
        echo "[Dry Run] Remove desktop entry: $TARGET_DESKTOP"
        echo "[Dry Run] pip uninstall -y gtk-emoji-picker"
    else
        [ -f "$TARGET_SERVICE" ] && rm -f "$TARGET_SERVICE" && echo "Removed $TARGET_SERVICE"
        [ -f "$TARGET_DESKTOP" ] && rm -f "$TARGET_DESKTOP" && echo "Removed $TARGET_DESKTOP"
        
        if command -v pip >/dev/null 2>&1; then
            pip uninstall -y gtk-emoji-picker >/dev/null 2>&1 || true
        fi
        
        if command -v systemctl >/dev/null 2>&1; then
            systemctl --user daemon-reload >/dev/null 2>&1 || true
        fi
        echo "Uninstallation complete."
    fi
    exit 0
fi

echo "=== Installing GTK Emoji Picker ==="
echo "Target Prefix     : $PREFIX"
echo "Binary Directory  : $BIN_DIR"
echo "Applications Dir  : $APP_DIR"
echo "Systemd User Dir  : $SYSTEMD_DIR"
echo "Enable Service    : $ENABLE_SERVICE"

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "[Dry Run] Create directory: $BIN_DIR"
    echo "[Dry Run] Create directory: $APP_DIR"
    echo "[Dry Run] Create directory: $SYSTEMD_DIR"
    echo "[Dry Run] Install python package via pip"
    echo "[Dry Run] Install desktop file to $APP_DIR/gtk-emoji-picker.desktop"
        echo "[Dry Run] Install systemd service to $SYSTEMD_DIR/$SERVICE_NAME"
    echo "[Dry Run] Run systemctl --user daemon-reload"
    [ "$ENABLE_SERVICE" = true ] && echo "[Dry Run] Run systemctl --user enable --now $SERVICE_NAME"
    echo "Dry run complete."
    exit 0
fi

# Ensure target directories exist
mkdir -p "$BIN_DIR" "$APP_DIR" "$SYSTEMD_DIR"

# Install Python package
echo "Installing Python package..."
if [ "$MODE" = "user" ]; then
    python3 -m pip install --user "$SCRIPT_DIR" --break-system-packages >/dev/null 2>&1 || \
    python3 -m pip install --user "$SCRIPT_DIR" >/dev/null 2>&1 || \
    pip install "$SCRIPT_DIR"
else
    python3 -m pip install "$SCRIPT_DIR"
fi

# Locate installed executables
DAEMON_EXEC="$BIN_DIR/gtk-emoji-picker-daemon"
PICKER_EXEC="$BIN_DIR/gtk-emoji-picker"

if command -v gtk-emoji-picker-daemon >/dev/null 2>&1; then
    DAEMON_EXEC="$(command -v gtk-emoji-picker-daemon)"
fi

if command -v gtk-emoji-picker >/dev/null 2>&1; then
    PICKER_EXEC="$(command -v gtk-emoji-picker)"
fi

# Install Desktop Entry
echo "Installing Desktop Entry..."
cp "$DESKTOP_FILE_SRC" "$APP_DIR/gtk-emoji-picker.desktop"
sed -i "s|^Exec=.*|Exec=$PICKER_EXEC|" "$APP_DIR/gtk-emoji-picker.desktop"
chmod 644 "$APP_DIR/gtk-emoji-picker.desktop"

# Install Systemd User Service
echo "Installing Systemd User Service..."
cp "$SERVICE_FILE_SRC" "$SYSTEMD_DIR/$SERVICE_NAME"
sed -i "s|^ExecStart=.*|ExecStart=$DAEMON_EXEC|" "$SYSTEMD_DIR/$SERVICE_NAME"
chmod 644 "$SYSTEMD_DIR/$SERVICE_NAME"

# Reload systemd user daemon
if command -v systemctl >/dev/null 2>&1; then
    echo "Reloading systemd user daemon..."
    systemctl --user daemon-reload || true

    if [ "$ENABLE_SERVICE" = true ]; then
        echo "Enabling and starting $SERVICE_NAME..."
        systemctl --user enable --now "$SERVICE_NAME" || true
    fi
fi

echo ""
echo "=== Installation Successfully Completed! ==="
echo "You can launch the picker using: gtk-emoji-picker"
echo "You can start the hotkey daemon using: gtk-emoji-picker-daemon"
echo "Or start systemd service: systemctl --user start $SERVICE_NAME"
