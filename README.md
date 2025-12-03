# Upwork Wayland Screenshot Bridge

A robust solution to run Upwork's time tracking application on GNOME Wayland sessions without X11 support.

## The Problem

Modern Linux distributions are transitioning to pure Wayland display servers:
- **Fedora 43+** has removed X11 session support entirely
- **Ubuntu 24.04+** defaults to Wayland
- **Other distributions** are following this trend

Upwork's desktop application requires X11 for screenshot functionality and refuses to run on Wayland, displaying:
> "Upwork screenshots are only available on Xorg sessions"

## The Solution

This bridge provides a D-Bus service that:
1. **Intercepts** Upwork's screenshot requests via the `org.gnome.Shell.Screenshot` D-Bus interface
2. **Captures** screenshots using Wayland-compatible tools (Flameshot or gnome-screenshot)
3. **Tricks** Upwork into thinking it's running on X11 while actually using Wayland

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    GNOME Wayland Session                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     D-Bus      ┌──────────────────────────┐  │
│  │              │ ──────────────▶│   Screenshot Bridge      │  │
│  │   Upwork     │                │   (screenshot.py)        │  │
│  │  (thinks     │                │                          │  │
│  │  it's X11)   │◀────────────── │  ┌──────────────────┐   │  │
│  │              │  screenshot    │  │ Flameshot        │   │  │
│  └──────────────┘    result      │  │ (primary)        │   │  │
│                                  │  └──────────────────┘   │  │
│                                  │  ┌──────────────────┐   │  │
│                                  │  │ gnome-screenshot │   │  │
│                                  │  │ (fallback)       │   │  │
│                                  │  └──────────────────┘   │  │
│                                  └──────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **Flameshot Integration**: Uses Flameshot for high-quality screenshots with area capture support
- **Automatic Fallback**: Falls back to gnome-screenshot if Flameshot is unavailable
- **Idle Time Tracking**: Implements `org.gnome.Mutter.IdleMonitor` for activity monitoring
- **Systemd Integration**: Optional systemd user service for automatic startup
- **Desktop Entry**: Integrates with your application menu

## Requirements

### System Requirements
- GNOME desktop environment on Wayland
- Python 3.7+
- Upwork desktop application

### Dependencies
- **flameshot** - Primary screenshot tool (recommended)
- **gnome-screenshot** - Fallback screenshot tool (usually pre-installed)
- **xdg-desktop-portal-gnome** - For screenshot permissions
- **dbus-next** - Python D-Bus library

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/upwork-wayland-bridge.git
cd upwork-wayland-bridge
./setup.sh
```

### 2. Launch Upwork

```bash
./upwork-launcher.sh
```

Or use the "Upwork (Wayland)" entry from your application menu.

## Manual Installation

### Fedora/RHEL

```bash
sudo dnf install flameshot xdg-desktop-portal xdg-desktop-portal-gnome
pip3 install --user dbus-next
```

### Ubuntu/Debian

```bash
sudo apt install flameshot xdg-desktop-portal xdg-desktop-portal-gnome
pip3 install --user dbus-next
```

### Arch Linux

```bash
sudo pacman -S flameshot xdg-desktop-portal xdg-desktop-portal-gnome
pip3 install --user dbus-next
```

### Make Scripts Executable

```bash
chmod +x screenshot.py upwork-launcher.sh setup.sh
```

## Usage

### Basic Usage

```bash
# Launch Upwork (starts bridge automatically)
./upwork-launcher.sh

# Check status
./upwork-launcher.sh --status

# Start bridge only (without launching Upwork)
./upwork-launcher.sh --start-bridge

# Stop bridge
./upwork-launcher.sh --stop-bridge

# Show help
./upwork-launcher.sh --help
```

### Debug Mode

```bash
# Run with debug output
./upwork-launcher.sh --debug

# View bridge logs
tail -f /tmp/upwork-bridge.log
```

### Systemd Service (Optional)

For automatic startup with your GNOME session:

```bash
# Enable the service
systemctl --user enable upwork-screenshot-bridge

# Start the service
systemctl --user start upwork-screenshot-bridge

# Check status
systemctl --user status upwork-screenshot-bridge
```

## Configuration

### Flameshot Permissions

On first run, Flameshot may ask for screenshot permission. Grant it to enable silent screenshots.

If you accidentally denied permission, reset it:

```bash
# Reset screenshot permissions
dbus-send --session --print-reply=literal \
    --dest=org.freedesktop.impl.portal.PermissionStore \
    /org/freedesktop/impl/portal/PermissionStore \
    org.freedesktop.impl.portal.PermissionStore.DeletePermission \
    string:'screenshot' string:'screenshot' string:''
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `UPWORK_BRIDGE_DEBUG` | Enable debug logging (0/1) | `1` |

## Troubleshooting

### Screenshots Not Working

1. **Check if bridge is running:**
   ```bash
   ./upwork-launcher.sh --status
   ```

2. **Test screenshot functionality:**
   ```bash
   flameshot full --path /tmp/test.png
   # or
   gnome-screenshot -f /tmp/test.png
   ```

3. **Check bridge logs:**
   ```bash
   cat /tmp/upwork-bridge.log
   ```

4. **Verify Wayland session:**
   ```bash
   echo $XDG_SESSION_TYPE
   # Should output: wayland
   ```

### Upwork Still Complains About Xorg

Make sure you're launching Upwork via the launcher script:
```bash
./upwork-launcher.sh
```

**Not** directly via `/opt/Upwork/upwork`.

### Permission Denied Errors

Reset Flameshot permissions using the setup script:
```bash
./setup.sh
# Select option 3 (Configure permissions only)
```

### Bridge Fails to Start

1. Check Python dependencies:
   ```bash
   python3 -c "import dbus_next; print('OK')"
   ```

2. Check if another service owns the D-Bus name:
   ```bash
   dbus-send --session --print-reply \
       --dest=org.freedesktop.DBus \
       /org/freedesktop/DBus \
       org.freedesktop.DBus.GetNameOwner \
       string:org.gnome.Shell.Screenshot
   ```

## How It Works

### D-Bus Interface Emulation

The bridge implements the `org.gnome.Shell.Screenshot` D-Bus interface:

| Method | Description |
|--------|-------------|
| `Screenshot()` | Captures full screen |
| `ScreenshotWindow()` | Captures focused window (falls back to full screen on Wayland) |
| `ScreenshotArea()` | Captures specific region |
| `FlashArea()` | Flashes area (no-op) |
| `SelectArea()` | Interactive area selection (returns default) |

### Screenshot Backends

1. **Flameshot** (Primary)
   - Full-featured screenshot tool
   - Supports area capture via `--region` flag
   - Works on GNOME Wayland with xdg-desktop-portal

2. **gnome-screenshot** (Fallback)
   - Native GNOME tool
   - Always available on GNOME systems
   - Limited to full-screen capture in non-interactive mode

### Idle Time Monitoring

The bridge also implements `org.gnome.Mutter.IdleMonitor`:
- Tracks user activity for Upwork's time tracking
- Connects to real GNOME IdleMonitor when available
- Falls back to internal tracking otherwise

## Limitations

- **Window-specific screenshots** fall back to full screen (Wayland security restriction)
- **GNOME-specific** - Other Wayland compositors (KDE, Sway) may need modifications
- **First-time permission** may be required for Flameshot

## Files

| File | Description |
|------|-------------|
| `screenshot.py` | D-Bus bridge service |
| `upwork-launcher.sh` | Launcher script |
| `setup.sh` | Interactive setup script |
| `README.md` | This documentation |
| `LICENSE` | MIT License |

## Contributing

Contributions welcome! Areas of interest:
- Testing on different distributions
- KDE Plasma Wayland support
- Improved window capture

## License

MIT License - See [LICENSE](LICENSE) for details.

## Credits

- Inspired by various Wayland screenshot bridge implementations
- Uses [python-dbus-next](https://github.com/altdesktop/python-dbus-next) for D-Bus communication
- Flameshot for screenshot functionality

## Disclaimer

This is an unofficial workaround. Use at your own risk. Ensure compliance with Upwork's Terms of Service.

---

## Research Sources

This solution was developed after extensive research:

- [Upwork Support - Troubleshoot desktop app (Linux)](https://support.upwork.com/hc/en-us/articles/211064108-Troubleshoot-desktop-app-Linux)
- [TecAdmin - Upwork Screenshots not supported on Wayland](https://tecadmin.net/upwork-screenshots-are-not-supported-on-wayland-please-switch-to-xorg/)
- [Flameshot - Wayland Help](https://flameshot.org/docs/guide/wayland-help/)
- [GNOME Shell Screenshot D-Bus Interface](https://github.com/vinzenz/gnome-shell/blob/master/data/org.gnome.Shell.Screenshot.xml)
- [XDG Desktop Portal - Screenshot](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Screenshot.html)
- [ArchWiki - XDG Desktop Portal](https://wiki.archlinux.org/title/XDG_Desktop_Portal)
- [python-dbus-next Documentation](https://github.com/altdesktop/python-dbus-next)
