#!/bin/bash
# =============================================================================
# Upwork Wayland Launcher
# =============================================================================
# This script launches Upwork with the Wayland screenshot bridge on GNOME.
#
# It performs the following:
# 1. Checks prerequisites (flameshot, Python, dbus-next)
# 2. Starts the screenshot bridge service if not running
# 3. Sets environment variables to make Upwork think it's on X11
# 4. Launches Upwork
#
# Author: Muhammad Rafey
# License: MIT
# =============================================================================

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_SCRIPT="$SCRIPT_DIR/screenshot.py"
BRIDGE_LOG="/tmp/upwork-bridge.log"
BRIDGE_PID_FILE="/tmp/upwork-bridge.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# =============================================================================
# Prerequisite Checks
# =============================================================================

check_prerequisites() {
    local missing=()

    # Check Python
    if ! check_command python3; then
        missing+=("python3")
    fi

    # Check for screenshot tool (flameshot preferred, gnome-screenshot fallback)
    if ! check_command flameshot && ! check_command gnome-screenshot; then
        missing+=("flameshot (or gnome-screenshot)")
    fi

    # Check for dbus-next Python module
    if ! python3 -c "import dbus_next" 2>/dev/null; then
        missing+=("python3-dbus-next (pip install dbus-next)")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing prerequisites:"
        for dep in "${missing[@]}"; do
            log_error "  - $dep"
        done
        echo ""
        echo "Install missing dependencies:"
        echo ""
        echo "  Fedora/RHEL:"
        echo "    sudo dnf install flameshot"
        echo "    pip3 install --user dbus-next"
        echo ""
        echo "  Ubuntu/Debian:"
        echo "    sudo apt install flameshot"
        echo "    pip3 install --user dbus-next"
        echo ""
        echo "  Arch Linux:"
        echo "    sudo pacman -S flameshot"
        echo "    pip3 install --user dbus-next"
        echo ""
        exit 1
    fi

    log_info "All prerequisites satisfied"
}

# =============================================================================
# Bridge Management
# =============================================================================

is_bridge_running() {
    if [ -f "$BRIDGE_PID_FILE" ]; then
        local pid
        pid=$(cat "$BRIDGE_PID_FILE" 2>/dev/null) || return 1
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi

    # Also check by process name - use more specific pattern
    if pgrep -f "python3 $BRIDGE_SCRIPT" > /dev/null 2>&1; then
        return 0
    fi

    return 1
}

start_bridge() {
    if is_bridge_running; then
        log_info "Screenshot bridge is already running"
        return 0
    fi

    log_info "Starting screenshot bridge..."

    # Preserve WAYLAND_DISPLAY for the bridge
    export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

    # Start bridge in background
    python3 "$BRIDGE_SCRIPT" >> "$BRIDGE_LOG" 2>&1 &
    local bridge_pid=$!
    echo "$bridge_pid" > "$BRIDGE_PID_FILE"

    # Wait for bridge to be ready
    log_info "Waiting for bridge to initialize..."
    sleep 2

    if kill -0 "$bridge_pid" 2>/dev/null; then
        log_info "Screenshot bridge started (PID: $bridge_pid)"
        log_info "Log file: $BRIDGE_LOG"
        return 0
    else
        log_error "Failed to start bridge. Check log: $BRIDGE_LOG"
        return 1
    fi
}

stop_bridge() {
    if [ -f "$BRIDGE_PID_FILE" ]; then
        local pid
        pid=$(cat "$BRIDGE_PID_FILE" 2>/dev/null) || true
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log_info "Stopping bridge (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            rm -f "$BRIDGE_PID_FILE"
        fi
    fi

    # Also kill any lingering processes - use specific pattern
    pkill -f "python3 $BRIDGE_SCRIPT" 2>/dev/null || true
}

# =============================================================================
# Upwork Launch
# =============================================================================

find_upwork() {
    local paths=(
        "/opt/Upwork/upwork"
        "/usr/bin/upwork"
        "/usr/local/bin/upwork"
        "$HOME/.local/bin/upwork"
    )

    for path in "${paths[@]}"; do
        if [ -x "$path" ]; then
            echo "$path"
            return 0
        fi
    done

    return 1
}

launch_upwork() {
    local upwork_path
    upwork_path=$(find_upwork) || {
        log_error "Upwork not found in standard locations"
        log_error "Searched: /opt/Upwork/upwork, /usr/bin/upwork, /usr/local/bin/upwork"
        exit 1
    }

    log_info "Found Upwork at: $upwork_path"

    # Set environment to make Upwork think it's running on X11
    # This is the key trick that makes Upwork work
    export XDG_SESSION_TYPE=x11

    # Unset WAYLAND_DISPLAY so Upwork doesn't detect Wayland
    unset WAYLAND_DISPLAY

    log_info "Launching Upwork..."
    exec "$upwork_path" "$@"
}

# =============================================================================
# Command Line Interface
# =============================================================================

show_help() {
    cat << EOF
Upwork Wayland Launcher

Usage: $(basename "$0") [OPTIONS] [-- UPWORK_ARGS]

Options:
  --help, -h        Show this help message
  --start-bridge    Only start the screenshot bridge (don't launch Upwork)
  --stop-bridge     Stop the screenshot bridge
  --status          Show bridge status
  --check           Check prerequisites only
  --debug           Enable debug mode

Examples:
  $(basename "$0")                    # Normal launch
  $(basename "$0") --start-bridge     # Start bridge only
  $(basename "$0") --status           # Check status
  $(basename "$0") -- --minimized     # Launch Upwork minimized

EOF
}

show_status() {
    echo "=== Upwork Wayland Bridge Status ==="
    echo ""

    # Check bridge
    if is_bridge_running; then
        local pid
        pid=$(pgrep -f "python3 $BRIDGE_SCRIPT" 2>/dev/null || cat "$BRIDGE_PID_FILE" 2>/dev/null || echo "unknown")
        echo "Screenshot Bridge: RUNNING (PID: $pid)"
    else
        echo "Screenshot Bridge: NOT RUNNING"
    fi

    # Check screenshot tools
    echo ""
    echo "Screenshot Tools:"
    if check_command flameshot; then
        echo "  - flameshot: AVAILABLE ($(flameshot --version 2>&1 | head -1))"
    else
        echo "  - flameshot: NOT INSTALLED"
    fi
    if check_command gnome-screenshot; then
        echo "  - gnome-screenshot: AVAILABLE"
    else
        echo "  - gnome-screenshot: NOT INSTALLED"
    fi

    # Check Wayland
    echo ""
    echo "Session Info:"
    echo "  - XDG_SESSION_TYPE: ${XDG_SESSION_TYPE:-not set}"
    echo "  - WAYLAND_DISPLAY: ${WAYLAND_DISPLAY:-not set}"

    # Check Upwork
    echo ""
    echo "Upwork:"
    local upwork_path
    if upwork_path=$(find_upwork 2>/dev/null); then
        echo "  - Found at: $upwork_path"
    else
        echo "  - NOT FOUND"
    fi

    # Recent log
    if [ -f "$BRIDGE_LOG" ]; then
        echo ""
        echo "Recent bridge log (last 5 lines):"
        tail -5 "$BRIDGE_LOG" 2>/dev/null | sed 's/^/  /'
    fi
}

# =============================================================================
# Main Entry Point
# =============================================================================

main() {
    local debug_mode=0

    # Parse command line options
    while [ $# -gt 0 ]; do
        case "$1" in
            --help|-h)
                show_help
                exit 0
                ;;
            --start-bridge)
                check_prerequisites
                start_bridge
                exit $?
                ;;
            --stop-bridge)
                stop_bridge
                log_info "Bridge stopped"
                exit 0
                ;;
            --status)
                show_status
                exit 0
                ;;
            --check)
                check_prerequisites
                log_info "All checks passed!"
                exit 0
                ;;
            --debug)
                export UPWORK_BRIDGE_DEBUG=1
                debug_mode=1
                shift
                ;;
            --)
                shift
                break
                ;;
            -*)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                break
                ;;
        esac
    done

    # Normal operation: check, start bridge, launch Upwork
    check_prerequisites
    start_bridge
    launch_upwork "$@"
}

main "$@"
