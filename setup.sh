#!/bin/bash
# =============================================================================
# Upwork Wayland Bridge - Setup Script
# =============================================================================
# This script helps set up the Upwork Wayland Bridge with proper permissions
# and configurations for GNOME Wayland.
#
# Author: Muhammad Rafey
# License: MIT
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
log_section() { echo -e "\n${BLUE}=== $1 ===${NC}\n"; }

# =============================================================================
# Detect Distribution
# =============================================================================

detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    elif [ -f /etc/fedora-release ]; then
        echo "fedora"
    elif [ -f /etc/debian_version ]; then
        echo "debian"
    else
        echo "unknown"
    fi
}

# =============================================================================
# Install Dependencies
# =============================================================================

install_dependencies() {
    log_section "Installing Dependencies"

    local distro=$(detect_distro)
    log_info "Detected distribution: $distro"

    case "$distro" in
        fedora|rhel|centos)
            log_info "Installing packages with dnf..."
            sudo dnf install -y flameshot python3-pip xdg-desktop-portal xdg-desktop-portal-gnome
            ;;
        ubuntu|debian|linuxmint|pop)
            log_info "Installing packages with apt..."
            sudo apt update
            sudo apt install -y flameshot python3-pip xdg-desktop-portal xdg-desktop-portal-gnome
            ;;
        arch|manjaro|endeavouros)
            log_info "Installing packages with pacman..."
            sudo pacman -S --noconfirm flameshot python-pip xdg-desktop-portal xdg-desktop-portal-gnome
            ;;
        opensuse*|suse*)
            log_info "Installing packages with zypper..."
            sudo zypper install -y flameshot python3-pip xdg-desktop-portal xdg-desktop-portal-gnome
            ;;
        *)
            log_warn "Unknown distribution: $distro"
            log_warn "Please install manually: flameshot, python3-pip, xdg-desktop-portal, xdg-desktop-portal-gnome"
            ;;
    esac

    # Install Python dependencies
    log_info "Installing Python dependencies..."
    # Try pip with --user first, fall back to --break-system-packages for PEP 668 systems
    if ! pip3 install --user dbus-next 2>/dev/null; then
        log_warn "Standard pip install failed, trying with --break-system-packages..."
        pip3 install --user --break-system-packages dbus-next 2>/dev/null || {
            log_error "Failed to install dbus-next. Try: pipx install dbus-next"
            log_error "Or create a virtual environment"
        }
    fi

    log_info "Dependencies installed successfully"
}

# =============================================================================
# Configure Flameshot Permissions
# =============================================================================

configure_flameshot_permissions() {
    log_section "Configuring Flameshot Permissions"

    log_info "Checking if Flameshot needs permission configuration..."

    # Check if flatpak permission-set is available
    if command -v flatpak &> /dev/null; then
        log_info "Setting Flameshot permissions via flatpak..."
        flatpak permission-set screenshot screenshot org.flameshot.Flameshot yes 2>/dev/null || true
    fi

    # Reset any denied permissions
    log_info "Resetting screenshot permissions in portal store..."
    dbus-send --session --print-reply=literal \
        --dest=org.freedesktop.impl.portal.PermissionStore \
        /org/freedesktop/impl/portal/PermissionStore \
        org.freedesktop.impl.portal.PermissionStore.DeletePermission \
        string:'screenshot' string:'screenshot' string:'' 2>/dev/null || true

    log_info "Flameshot permissions configured"
    log_warn "Note: You may need to grant permission on first screenshot"
}

# =============================================================================
# Create Desktop Entry
# =============================================================================

create_desktop_entry() {
    log_section "Creating Desktop Entry"

    local desktop_dir="$HOME/.local/share/applications"
    local desktop_file="$desktop_dir/upwork-wayland.desktop"
    local launcher_path="$SCRIPT_DIR/upwork-launcher.sh"

    mkdir -p "$desktop_dir"

    # Find Upwork icon
    local icon_path="/opt/Upwork/resources/app.asar.unpacked/assets/icon.png"
    if [ ! -f "$icon_path" ]; then
        icon_path="upwork"  # Use system icon
    fi

    cat > "$desktop_file" << EOF
[Desktop Entry]
Name=Upwork (Wayland)
Comment=Upwork Desktop App with Wayland Screenshot Support
Exec=$launcher_path %U
Icon=$icon_path
Terminal=false
Type=Application
Categories=Network;Office;
Keywords=upwork;freelance;work;time;tracking;
StartupNotify=true
StartupWMClass=Upwork
EOF

    log_info "Desktop entry created: $desktop_file"
    log_info "You can now launch 'Upwork (Wayland)' from your application menu"

    # Update desktop database
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$desktop_dir" 2>/dev/null || true
    fi
}

# =============================================================================
# Create Systemd User Service
# =============================================================================

create_systemd_service() {
    log_section "Creating Systemd User Service (Optional)"

    local service_dir="$HOME/.config/systemd/user"
    local service_file="$service_dir/upwork-screenshot-bridge.service"
    local bridge_path="$SCRIPT_DIR/screenshot.py"

    mkdir -p "$service_dir"

    cat > "$service_file" << EOF
[Unit]
Description=Upwork Wayland Screenshot Bridge
Documentation=https://github.com/yourusername/upwork-wayland-bridge
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $bridge_path
Restart=on-failure
RestartSec=5
Environment=UPWORK_BRIDGE_DEBUG=0

[Install]
WantedBy=graphical-session.target
EOF

    log_info "Systemd service created: $service_file"
    log_info ""
    log_info "To enable automatic startup:"
    log_info "  systemctl --user enable upwork-screenshot-bridge"
    log_info ""
    log_info "To start the service now:"
    log_info "  systemctl --user start upwork-screenshot-bridge"
    log_info ""
    log_info "To check status:"
    log_info "  systemctl --user status upwork-screenshot-bridge"

    # Reload systemd
    systemctl --user daemon-reload 2>/dev/null || true
}

# =============================================================================
# Test Screenshot Functionality
# =============================================================================

test_screenshot() {
    log_section "Testing Screenshot Functionality"

    local test_file="/tmp/upwork-bridge-test-$(date +%s).png"

    log_info "Testing Flameshot screenshot capture..."

    # Set up environment for test
    export QT_QPA_PLATFORM=wayland

    # Helper function to get file size portably
    get_file_size() {
        wc -c < "$1" 2>/dev/null | tr -d ' '
    }

    if flameshot full --path "$test_file" 2>/dev/null; then
        if [ -f "$test_file" ]; then
            local size
            size=$(get_file_size "$test_file")
            if [ "${size:-0}" -gt 0 ]; then
                log_info "Screenshot test PASSED!"
                log_info "Test file: $test_file ($(du -h "$test_file" | cut -f1))"
                rm -f "$test_file"
                return 0
            fi
        fi
    fi

    log_warn "Flameshot test failed, trying gnome-screenshot..."

    if gnome-screenshot -f "$test_file" 2>/dev/null; then
        if [ -f "$test_file" ]; then
            local size
            size=$(get_file_size "$test_file")
            if [ "${size:-0}" -gt 0 ]; then
                log_info "gnome-screenshot test PASSED!"
                log_info "Test file: $test_file ($(du -h "$test_file" | cut -f1))"
                rm -f "$test_file"
                return 0
            fi
        fi
    fi

    log_error "Screenshot test FAILED!"
    log_error "Please ensure you're running on a GNOME Wayland session"
    log_error "and that screenshot permissions are granted"
    return 1
}

# =============================================================================
# Make Scripts Executable
# =============================================================================

make_executable() {
    log_section "Setting Permissions"

    chmod +x "$SCRIPT_DIR/screenshot.py"
    chmod +x "$SCRIPT_DIR/upwork-launcher.sh"
    chmod +x "$SCRIPT_DIR/setup.sh"

    log_info "Scripts are now executable"
}

# =============================================================================
# Show Summary
# =============================================================================

show_summary() {
    log_section "Setup Complete!"

    echo "The Upwork Wayland Bridge has been configured."
    echo ""
    echo "Quick Start:"
    echo "  1. Launch Upwork using: ./upwork-launcher.sh"
    echo "  2. Or use the 'Upwork (Wayland)' entry in your app menu"
    echo ""
    echo "Commands:"
    echo "  ./upwork-launcher.sh              # Launch Upwork"
    echo "  ./upwork-launcher.sh --status     # Check bridge status"
    echo "  ./upwork-launcher.sh --start-bridge  # Start bridge only"
    echo ""
    echo "Troubleshooting:"
    echo "  - Check logs: cat /tmp/upwork-bridge.log"
    echo "  - Test screenshot: flameshot full --path /tmp/test.png"
    echo "  - Reset permissions: Run this setup script again"
    echo ""
    echo "Documentation: See README.md for more details"
}

# =============================================================================
# Main Menu
# =============================================================================

show_menu() {
    echo ""
    echo "Upwork Wayland Bridge Setup"
    echo "=========================="
    echo ""
    echo "1) Full setup (recommended for first time)"
    echo "2) Install dependencies only"
    echo "3) Configure permissions only"
    echo "4) Create desktop entry only"
    echo "5) Create systemd service only"
    echo "6) Test screenshot functionality"
    echo "7) Exit"
    echo ""
    read -rp "Select option [1-7]: " choice

    case "$choice" in
        1)
            make_executable
            install_dependencies
            configure_flameshot_permissions
            create_desktop_entry
            create_systemd_service
            test_screenshot || true
            show_summary
            ;;
        2)
            install_dependencies
            ;;
        3)
            configure_flameshot_permissions
            ;;
        4)
            create_desktop_entry
            ;;
        5)
            create_systemd_service
            ;;
        6)
            test_screenshot
            ;;
        7)
            log_info "Exiting"
            exit 0
            ;;
        *)
            log_error "Invalid option"
            show_menu
            ;;
    esac
}

# =============================================================================
# Entry Point
# =============================================================================

main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║        Upwork Wayland Screenshot Bridge Setup            ║"
    echo "╚══════════════════════════════════════════════════════════╝"

    # Check if running on Wayland
    if [ "$XDG_SESSION_TYPE" != "wayland" ]; then
        log_warn "Not running on Wayland (XDG_SESSION_TYPE=$XDG_SESSION_TYPE)"
        log_warn "This tool is designed for GNOME Wayland sessions"
        echo ""
        read -rp "Continue anyway? [y/N]: " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            exit 0
        fi
    fi

    # Handle command line options
    case "${1:-}" in
        --auto|--unattended)
            log_info "Running unattended setup..."
            make_executable
            install_dependencies
            configure_flameshot_permissions
            create_desktop_entry
            create_systemd_service
            test_screenshot || true
            show_summary
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --auto      Run full unattended setup"
            echo "  --help      Show this help message"
            echo ""
            echo "Without options, shows interactive menu."
            ;;
        *)
            show_menu
            ;;
    esac
}

main "$@"
