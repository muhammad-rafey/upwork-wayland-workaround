#!/bin/bash
# install.sh - Install desktop launcher for Upwork Wayland Bridge

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="${DESKTOP_DIR}/upwork.desktop"

# Ensure scripts are executable
chmod +x "$SCRIPT_DIR/screenshot.py" "$SCRIPT_DIR/upwork-launcher.sh"

# Find icon from system desktop file, fall back to theme name
ICON="upwork"
SYSTEM_DESKTOP="/usr/share/applications/upwork.desktop"
if [ -f "$SYSTEM_DESKTOP" ]; then
    ORIG_ICON=$(grep -m1 "^Icon=" "$SYSTEM_DESKTOP" | cut -d= -f2-)
    [ -n "$ORIG_ICON" ] && ICON="$ORIG_ICON"
fi

mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=Upwork
Comment=Upwork Desktop Application
Exec=${SCRIPT_DIR}/upwork-launcher.sh %U
Icon=${ICON}
Terminal=false
Type=Application
StartupWMClass=Upwork
MimeType=x-scheme-handler/upwork;
Categories=Utility;
EOF

# Update desktop database so the DE picks up the change
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null
fi

echo "Desktop launcher installed: $DESKTOP_FILE"
