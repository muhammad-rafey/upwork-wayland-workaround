#!/usr/bin/env python3
"""
Upwork Wayland Screenshot Bridge
================================
A D-Bus service that bridges Upwork's screenshot requests to Wayland-compatible
screenshot tools on GNOME.

This service emulates the org.gnome.Shell.Screenshot D-Bus interface and uses
Flameshot (primary) or gnome-screenshot (fallback) to capture screenshots.

Key Features:
- Uses Flameshot for full-featured screenshot capture
- Falls back to gnome-screenshot if Flameshot is unavailable
- Implements org.gnome.Mutter.IdleMonitor for activity tracking
- Proper Wayland environment handling

Author: Muhammad Rafey
License: MIT
"""

import asyncio
import datetime as dt
import sys
import os
import shutil
from pathlib import Path
from typing import List

from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, signal
from dbus_next import BusType, DBusError


# ============================================================================
# Configuration
# ============================================================================

DEBUG = os.environ.get('UPWORK_BRIDGE_DEBUG', '1') == '1'
SCREENSHOT_TIMEOUT = 30  # seconds


# ============================================================================
# Logging Utilities
# ============================================================================

def debug(*msg):
    """Print debug messages to stderr."""
    if DEBUG:
        timestamp = dt.datetime.now().strftime('%H:%M:%S')
        try:
            print(f'[{timestamp}]', *msg, file=sys.stderr, flush=True)
        except OSError:
            pass


def info(*msg):
    """Print info messages to stderr (always shown)."""
    timestamp = dt.datetime.now().strftime('%H:%M:%S')
    try:
        print(f'[{timestamp}] INFO:', *msg, file=sys.stderr, flush=True)
    except OSError:
        pass


def error(*msg):
    """Print error messages to stderr (always shown)."""
    timestamp = dt.datetime.now().strftime('%H:%M:%S')
    try:
        print(f'[{timestamp}] ERROR:', *msg, file=sys.stderr, flush=True)
    except OSError:
        pass


# ============================================================================
# Screenshot Backend Classes
# ============================================================================

class ScreenshotBackend:
    """Base class for screenshot backends."""

    name: str = "base"

    def is_available(self) -> bool:
        """Check if this backend is available on the system."""
        raise NotImplementedError

    def capture_full_sync(self, filename: str, include_cursor: bool = False) -> bool:
        """Capture full screen screenshot (synchronous)."""
        raise NotImplementedError

    def capture_area_sync(self, filename: str, x: int, y: int,
                         width: int, height: int) -> bool:
        """Capture area screenshot (synchronous)."""
        raise NotImplementedError


class FlameshotBackend(ScreenshotBackend):
    """
    Flameshot-based screenshot backend.

    Flameshot is a powerful screenshot tool that works well on GNOME Wayland
    when properly configured. It requires initial permission grant via
    xdg-desktop-portal.

    Commands used:
    - Full screen: flameshot full --path /path/to/file.png
    - Area: flameshot full --region WxH+X+Y --path /path/to/file.png
    """

    name = "flameshot"

    def __init__(self):
        self._binary = shutil.which('flameshot')
        self._env = self._prepare_environment()

    def _prepare_environment(self) -> dict:
        """Prepare environment variables for Flameshot on Wayland."""
        env = os.environ.copy()
        # Ensure Flameshot uses Wayland properly
        env['QT_QPA_PLATFORM'] = 'wayland'
        # Don't override XDG_SESSION_TYPE for flameshot - it needs to know it's Wayland
        if 'XDG_SESSION_TYPE' in env and env['XDG_SESSION_TYPE'] == 'x11':
            env['XDG_SESSION_TYPE'] = 'wayland'
        return env

    def is_available(self) -> bool:
        """Check if Flameshot is installed."""
        return self._binary is not None

    def capture_full_sync(self, filename: str, include_cursor: bool = False) -> bool:
        """Capture full screen using Flameshot (synchronous)."""
        import subprocess
        debug(f'[Flameshot] Capturing full screen to: {filename}')

        # Ensure directory exists
        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        # Build command
        cmd = [self._binary, 'full', '--path', filename]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env,
                timeout=SCREENSHOT_TIMEOUT
            )

            if result.returncode != 0:
                debug(f'[Flameshot] Command failed: {result.stderr.decode()}')
                return False

            # Verify file was created
            if Path(filename).exists():
                debug(f'[Flameshot] Screenshot saved successfully')
                return True
            else:
                debug(f'[Flameshot] File not created')
                return False

        except subprocess.TimeoutExpired:
            error('[Flameshot] Screenshot timed out')
            return False
        except Exception as e:
            error(f'[Flameshot] Error: {e}')
            return False

    def capture_area_sync(self, filename: str, x: int, y: int,
                         width: int, height: int) -> bool:
        """Capture specific area using Flameshot (synchronous)."""
        import subprocess
        debug(f'[Flameshot] Capturing area {x},{y} {width}x{height} to: {filename}')

        # Ensure directory exists
        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        # Build region string: WxH+X+Y
        region = f'{width}x{height}+{x}+{y}'
        cmd = [self._binary, 'full', '--region', region, '--path', filename]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env,
                timeout=SCREENSHOT_TIMEOUT
            )

            if result.returncode != 0:
                debug(f'[Flameshot] Area capture failed: {result.stderr.decode()}')
                return False

            if Path(filename).exists():
                debug(f'[Flameshot] Area screenshot saved successfully')
                return True
            else:
                debug(f'[Flameshot] File not created')
                return False

        except subprocess.TimeoutExpired:
            error('[Flameshot] Area screenshot timed out')
            return False
        except Exception as e:
            error(f'[Flameshot] Error: {e}')
            return False


class GnomeScreenshotBackend(ScreenshotBackend):
    """
    gnome-screenshot-based backend.

    This is the fallback backend using GNOME's native screenshot tool.
    It's always available on GNOME systems.

    Commands used:
    - Full screen: gnome-screenshot -f /path/to/file.png
    - Window: gnome-screenshot -w -f /path/to/file.png

    Note: gnome-screenshot doesn't support area capture in non-interactive mode.
    """

    name = "gnome-screenshot"

    def __init__(self):
        self._binary = shutil.which('gnome-screenshot')
        self._env = self._prepare_environment()

    def _prepare_environment(self) -> dict:
        """Prepare environment for gnome-screenshot."""
        env = os.environ.copy()
        # gnome-screenshot needs proper Wayland display
        if 'WAYLAND_DISPLAY' not in env:
            env['WAYLAND_DISPLAY'] = 'wayland-0'
        return env

    def is_available(self) -> bool:
        """Check if gnome-screenshot is installed."""
        return self._binary is not None

    def capture_full_sync(self, filename: str, include_cursor: bool = False) -> bool:
        """Capture full screen using gnome-screenshot (synchronous)."""
        import subprocess
        debug(f'[gnome-screenshot] Capturing full screen to: {filename}')

        # Ensure directory exists
        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        # Build command
        cmd = [self._binary, '-f', filename]
        if include_cursor:
            cmd.append('-p')  # Include pointer

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env,
                timeout=SCREENSHOT_TIMEOUT
            )

            if result.returncode != 0:
                debug(f'[gnome-screenshot] Command failed: {result.stderr.decode()}')
                return False

            if Path(filename).exists():
                debug(f'[gnome-screenshot] Screenshot saved successfully')
                return True
            else:
                debug(f'[gnome-screenshot] File not created')
                return False

        except subprocess.TimeoutExpired:
            error('[gnome-screenshot] Screenshot timed out')
            return False
        except Exception as e:
            error(f'[gnome-screenshot] Error: {e}')
            return False

    def capture_area_sync(self, filename: str, x: int, y: int,
                         width: int, height: int) -> bool:
        """
        Capture area - gnome-screenshot doesn't support this in non-interactive mode.
        Falls back to full screen capture.
        """
        debug(f'[gnome-screenshot] Area capture not supported, using full screen')
        return self.capture_full_sync(filename)


# ============================================================================
# Screenshot Manager
# ============================================================================

class ScreenshotManager:
    """
    Manages multiple screenshot backends with automatic fallback.

    Tries backends in order of preference:
    1. Flameshot (best features)
    2. gnome-screenshot (native fallback)
    """

    def __init__(self):
        self.backends: List[ScreenshotBackend] = []
        self._initialize_backends()

    def _initialize_backends(self):
        """Initialize and check available backends."""
        # Add backends in order of preference
        candidates = [
            FlameshotBackend(),
            GnomeScreenshotBackend(),
        ]

        for backend in candidates:
            if backend.is_available():
                self.backends.append(backend)
                info(f'Backend available: {backend.name}')
            else:
                debug(f'Backend not available: {backend.name}')

        if not self.backends:
            error('No screenshot backends available!')
            error('Please install flameshot or gnome-screenshot')

    def capture_full_sync(self, filename: str, include_cursor: bool = False) -> bool:
        """Capture full screen using first available backend (synchronous)."""
        for backend in self.backends:
            debug(f'Trying backend: {backend.name}')
            result = backend.capture_full_sync(filename, include_cursor)
            if result:
                return True
            debug(f'Backend {backend.name} failed, trying next...')

        error('All backends failed for full screen capture')
        return False

    def capture_area_sync(self, filename: str, x: int, y: int,
                         width: int, height: int) -> bool:
        """Capture area using first available backend (synchronous)."""
        for backend in self.backends:
            debug(f'Trying backend: {backend.name}')
            result = backend.capture_area_sync(filename, x, y, width, height)
            if result:
                return True
            debug(f'Backend {backend.name} failed, trying next...')

        error('All backends failed for area capture')
        return False


# ============================================================================
# D-Bus Screenshot Interface
# ============================================================================

class ScreenshotInterface(ServiceInterface):
    """
    D-Bus interface implementing org.gnome.Shell.Screenshot.

    This interface is what Upwork uses to request screenshots.
    We intercept these calls and use our screenshot manager to
    capture the screen using Wayland-compatible tools.
    """

    def __init__(self, manager: ScreenshotManager):
        super().__init__('org.gnome.Shell.Screenshot')
        self.manager = manager

    def _resolve_filename(self, filename: str) -> str:
        """
        Resolve filename to absolute path.

        If filename is a basename (no directory), save to XDG_PICTURES_DIR
        or home directory.
        """
        if os.path.isabs(filename):
            return filename

        # Try XDG_PICTURES_DIR first
        pictures_dir = os.environ.get('XDG_PICTURES_DIR')
        if pictures_dir and os.path.isdir(pictures_dir):
            return os.path.join(pictures_dir, filename)

        # Fall back to home directory
        home = os.path.expanduser('~')
        return os.path.join(home, filename)

    @method()
    def Screenshot(self, include_cursor: 'b', flash: 'b', filename: 's') -> 'bs':
        """
        Take a full screen screenshot.

        Args:
            include_cursor: Whether to include the cursor
            flash: Whether to flash the screen (ignored)
            filename: Target filename

        Returns:
            Tuple of (success, filename_used)
        """
        debug(f'Screenshot() called: cursor={include_cursor}, file={filename}')

        resolved_filename = self._resolve_filename(filename)

        try:
            success = self.manager.capture_full_sync(resolved_filename, include_cursor)
            if success:
                info(f'Screenshot saved: {resolved_filename}')
                return [True, resolved_filename]
            else:
                error(f'Screenshot failed: {resolved_filename}')
                return [False, '']
        except Exception as e:
            error(f'Screenshot exception: {e}')
            return [False, '']

    @method()
    def ScreenshotWindow(self, include_frame: 'b', include_cursor: 'b',
                         flash: 'b', filename: 's') -> 'bs':
        """
        Take a screenshot of the focused window.

        Note: On Wayland, window-specific capture is restricted.
        Falls back to full screen capture.

        Args:
            include_frame: Whether to include window frame (ignored)
            include_cursor: Whether to include the cursor
            flash: Whether to flash the window (ignored)
            filename: Target filename

        Returns:
            Tuple of (success, filename_used)
        """
        debug(f'ScreenshotWindow() called: file={filename}')
        debug('Note: Window capture falls back to full screen on Wayland')

        # Fall back to full screen capture
        return self.Screenshot(include_cursor, flash, filename)

    @method()
    def ScreenshotArea(self, x: 'i', y: 'i', width: 'i', height: 'i',
                       flash: 'b', filename: 's') -> 'bs':
        """
        Take a screenshot of a specific area.

        Args:
            x: X coordinate of area
            y: Y coordinate of area
            width: Width of area
            height: Height of area
            flash: Whether to flash the area (ignored)
            filename: Target filename

        Returns:
            Tuple of (success, filename_used)
        """
        debug(f'ScreenshotArea() called: {x},{y} {width}x{height} -> {filename}')

        resolved_filename = self._resolve_filename(filename)

        try:
            success = self.manager.capture_area_sync(resolved_filename, x, y, width, height)
            if success:
                info(f'Area screenshot saved: {resolved_filename}')
                return [True, resolved_filename]
            else:
                error(f'Area screenshot failed: {resolved_filename}')
                return [False, '']
        except Exception as e:
            error(f'Area screenshot exception: {e}')
            return [False, '']

    @method()
    def FlashArea(self, x: 'i', y: 'i', width: 'i', height: 'i') -> '':
        """Flash a specific area of the screen (no-op)."""
        debug(f'FlashArea() called: {x},{y} {width}x{height} - ignored')
        return None

    @method()
    def SelectArea(self) -> 'iiii':
        """
        Interactively select an area.

        Returns a default area since we can't do interactive selection
        from a background service.
        """
        debug('SelectArea() called - returning default area')
        return [0, 0, 1920, 1080]


# ============================================================================
# D-Bus Idle Monitor Interface
# ============================================================================

class IdleMonitorInterface(ServiceInterface):
    """
    D-Bus interface implementing org.gnome.Mutter.IdleMonitor.

    This interface provides idle time tracking for Upwork's activity monitoring.
    We try to connect to the real GNOME IdleMonitor first, falling back to
    our own tracking if unavailable.
    """

    def __init__(self):
        super().__init__('org.gnome.Mutter.IdleMonitor')
        self.last_active = dt.datetime.utcnow()
        self._watch_id_counter = 1
        self._watches = {}
        self._real_monitor = None
        self._use_real_monitor = False

    async def try_connect_real_monitor(self, bus: MessageBus):
        """Try to connect to the real GNOME IdleMonitor."""
        try:
            introspection = await bus.introspect(
                'org.gnome.Mutter.IdleMonitor',
                '/org/gnome/Mutter/IdleMonitor/Core'
            )
            proxy = bus.get_proxy_object(
                'org.gnome.Mutter.IdleMonitor',
                '/org/gnome/Mutter/IdleMonitor/Core',
                introspection
            )
            self._real_monitor = proxy.get_interface('org.gnome.Mutter.IdleMonitor')
            self._use_real_monitor = True
            info('Connected to real GNOME IdleMonitor')
        except Exception as e:
            debug(f'Could not connect to real IdleMonitor: {e}')
            debug('Using internal idle tracking')

    def _update_activity(self):
        """Update last activity timestamp."""
        self.last_active = dt.datetime.utcnow()

    @method()
    def GetIdletime(self) -> 't':
        """
        Get the current idle time in milliseconds.

        Returns:
            Idle time in milliseconds
        """
        if self._use_real_monitor and self._real_monitor:
            try:
                # This would need async handling in production
                return 0
            except Exception:
                pass

        delta = dt.datetime.utcnow() - self.last_active
        idle_ms = int(delta.total_seconds() * 1000)
        debug(f'GetIdletime() -> {idle_ms}ms')
        return idle_ms

    @method()
    def AddIdleWatch(self, interval: 't') -> 'u':
        """
        Add a watch for when idle time reaches a threshold.

        Args:
            interval: Idle threshold in milliseconds

        Returns:
            Watch ID
        """
        watch_id = self._watch_id_counter
        self._watch_id_counter += 1
        self._watches[watch_id] = {'type': 'idle', 'interval': interval}
        debug(f'AddIdleWatch({interval}ms) -> {watch_id}')
        return watch_id

    @method()
    def AddUserActiveWatch(self) -> 'u':
        """
        Add a watch for when user becomes active.

        Returns:
            Watch ID
        """
        watch_id = self._watch_id_counter
        self._watch_id_counter += 1
        self._watches[watch_id] = {'type': 'active'}
        debug(f'AddUserActiveWatch() -> {watch_id}')
        return watch_id

    @method()
    def RemoveWatch(self, id: 'u') -> '':
        """
        Remove a previously added watch.

        Args:
            id: Watch ID to remove
        """
        if id in self._watches:
            del self._watches[id]
            debug(f'RemoveWatch({id}) - removed')
        else:
            debug(f'RemoveWatch({id}) - not found')
        return None

    @method()
    def ResetIdletime(self) -> '':
        """Reset the idle time counter."""
        self._update_activity()
        debug('ResetIdletime() - reset')
        return None

    @signal()
    def WatchFired(self, id: 'u') -> 'u':
        """Signal emitted when a watch fires."""
        return id


# ============================================================================
# Main Application
# ============================================================================

async def main():
    """Main entry point for the screenshot bridge."""
    info('=' * 60)
    info('Upwork Wayland Screenshot Bridge')
    info('=' * 60)

    # Initialize screenshot manager
    manager = ScreenshotManager()

    if not manager.backends:
        error('No screenshot backends available. Exiting.')
        sys.exit(1)

    # Connect to D-Bus
    try:
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        info('Connected to D-Bus session bus')
    except Exception as e:
        error(f'Failed to connect to D-Bus: {e}')
        sys.exit(1)

    # Create interfaces
    screenshot = ScreenshotInterface(manager)
    idle = IdleMonitorInterface()

    # Try to connect to real idle monitor
    await idle.try_connect_real_monitor(bus)

    # Export interfaces
    bus.export('/org/gnome/Shell/Screenshot', screenshot)
    info('Exported /org/gnome/Shell/Screenshot')

    bus.export('/org/gnome/Mutter/IdleMonitor/Core', idle)
    info('Exported /org/gnome/Mutter/IdleMonitor/Core')

    # Request bus names
    try:
        await bus.request_name('org.gnome.Shell.Screenshot')
        info('Claimed name: org.gnome.Shell.Screenshot')
    except DBusError as e:
        error(f'Failed to claim Screenshot name: {e}')
        error('Another service may already own this name')
        sys.exit(1)

    try:
        await bus.request_name('org.gnome.Mutter.IdleMonitor')
        info('Claimed name: org.gnome.Mutter.IdleMonitor')
    except DBusError as e:
        debug(f'Could not claim IdleMonitor name: {e}')
        debug('This is OK if GNOME Shell is running')

    info('-' * 60)
    info('Bridge is ready! Waiting for screenshot requests...')
    info('-' * 60)

    # Keep running forever - use Event for clean shutdown
    stop_event = asyncio.Event()

    # Handle signals for graceful shutdown
    import signal

    def handle_signal(signum, frame):
        info(f'Received signal {signum}, shutting down...')
        stop_event.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass

    info('Bridge shutting down...')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        info('Stopped by user')
    except Exception as e:
        error(f'Unexpected error: {e}')
        sys.exit(1)
