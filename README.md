# Upwork Wayland Bridge for GNOME

A workaround to run Upwork's time tracking application on GNOME Wayland sessions without X11 support.

## Problem

Modern GNOME installations are moving to pure Wayland sessions, with some distributions (like Fedora 43+) completely removing X11 session support. Upwork's desktop application requires X11 for screenshot functionality and will refuse to run on Wayland, displaying an error: "Upwork screenshots are only available on Xorg sessions."

## Solution

This bridge consists of two components:

1. **screenshot.py** - A D-Bus service that emulates GNOME Shell's screenshot API, using `grim` to capture screenshots on Wayland
2. **upwork-launcher.sh** - A launcher script that tricks Upwork into thinking it's running on X11 while actually using Wayland

## Requirements

- GNOME desktop environment running on Wayland
- Python 3.5+
- Upwork desktop application
- Required packages:
  - `grim` - Wayland screenshot utility
  - `swayidle` - For activity tracking (optional but recommended)
  - `dbus-next` - Python D-Bus library

## Compatibility

Tested and working on:
- Fedora 43+ (GNOME on Wayland)
- Ubuntu 24.04+ (GNOME on Wayland)
- Arch Linux (GNOME on Wayland)
- Any Linux distribution running GNOME on pure Wayland

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/upwork-wayland-bridge.git
cd upwork-wayland-bridge
```

### 2. Install dependencies

**Fedora/RHEL:**
```bash
sudo dnf install grim swayidle
pip3 install --user dbus-next
```

**Ubuntu/Debian:**
```bash
sudo apt install grim swayidle
pip3 install --user dbus-next
```

**Arch Linux:**
```bash
sudo pacman -S grim swayidle
pip3 install --user dbus-next
```

### 3. Make scripts executable
```bash
chmod +x screenshot.py
chmod +x upwork-launcher.sh
```

## Usage

### Quick Start

Simply run the launcher script from the project directory:
```bash
./upwork-launcher.sh
```

The launcher will automatically:
- Start the screenshot bridge if not already running
- Launch Upwork with the proper environment variables
- Enable screenshot functionality

### Make it permanent

#### Option 1: Add to PATH

Add to your `~/.zshrc` or `~/.bashrc`:
```bash
export PATH="$HOME/path/to/upwork-wayland-bridge:$PATH"
```

Then reload your shell:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

#### Option 2: Create an alias

Add to your `~/.zshrc` or `~/.bashrc`:
```bash
alias upwork='~/path/to/upwork-wayland-bridge/upwork-launcher.sh'
```

#### Option 3: Install desktop launcher
```bash
./install.sh
```

This generates a clean desktop file at `~/.local/share/applications/upwork.desktop` pointing to the launcher, preserves the Upwork icon, and updates the desktop database. You can then launch Upwork from your application menu.

To uninstall the launcher:
```bash
rm ~/.local/share/applications/upwork.desktop
```

## How It Works

1. **screenshot.py** creates a D-Bus service that implements the `org.gnome.Shell.Screenshot` interface
2. When Upwork requests a screenshot via D-Bus, the bridge uses `grim` to capture the screen
3. **upwork-launcher.sh** sets environment variables (`XDG_SESSION_TYPE=x11`) to make Upwork believe it's running on X11
4. Upwork operates normally, taking screenshots through the bridge without knowing it's actually on Wayland

## Troubleshooting

### Screenshots not working

Check if the bridge is running:
```bash
pgrep -af screenshot.py
```

Check for errors:
```bash
python3 screenshot.py
# Look for error messages in the output
```

### Upwork still complains about Xorg

Make sure you're launching Upwork via the launcher script, not directly. The environment variables must be set.

### Bridge fails to start

Ensure `grim` is installed and working:
```bash
grim /tmp/test.png
# Check if the screenshot was created
ls -lh /tmp/test.png
```

### Verify you're running Wayland

Check your current session type:
```bash
echo $XDG_SESSION_TYPE
# Should output: wayland
```

If you're already on X11, this bridge is not needed.

## Limitations

- Window-specific screenshots fall back to full screen capture (Wayland security restriction)
- Designed specifically for GNOME on Wayland; other Wayland compositors (Sway, KDE) may require adjustments
- Idle time tracking requires `swayidle`

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests, especially for:
- Testing on different distributions
- Improvements to window capture functionality
- Support for other Wayland compositors

## License

MIT License - Feel free to use and modify as needed.

## Credits

Original bridge script concept adapted from various Wayland screenshot bridge implementations. Updated and tested for modern GNOME Wayland sessions.

## Disclaimer

This is an unofficial workaround. Use at your own risk. Always ensure you comply with Upwork's terms of service.

---

### FAQ

**Q: Will this work on KDE Plasma Wayland?**  
A: This is designed for GNOME. KDE uses different D-Bus interfaces, so modifications would be needed.

**Q: Is this safe to use?**  
A: Yes, it only provides a screenshot interface. It doesn't modify Upwork or bypass any security features.

**Q: Can I use this with other applications that require X11 screenshots?**  
A: Potentially yes, if they use the same GNOME Shell screenshot D-Bus interface.

**Q: Do I need to run this every time I start my computer?**  
A: If you set it up via the desktop launcher (Option 3), it will start automatically when you launch Upwork from your application menu.