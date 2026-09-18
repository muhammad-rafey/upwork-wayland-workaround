#!/usr/bin/env python3
# screenshot.py - Bridge script for Upwork on Wayland
import asyncio
import datetime as dt
import subprocess
import sys
import os

from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method
from dbus_next import BusType, DBusError


def debug(*msg):
    try:
        print(*msg, file=sys.stderr, flush=True)
    except OSError:
        pass


class ScreenshotInterface(ServiceInterface):
    def __init__(self):
        super().__init__('org.gnome.Shell.Screenshot')

    @method()
    def Screenshot(self, include_cursor: 'b', flash: 'b', filename: 's') -> 'bs':
        debug('Screenshot call:', filename)
        try:
            os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
            cmd = ['grim', filename]
            if include_cursor:
                cmd.insert(1, '-c')
            subprocess.run(cmd, check=True)
            debug('Screenshot saved:', filename)
            return [True, filename]
        except Exception as e:
            debug('Screenshot error:', e)
            return [False, '']

    @method()
    def ScreenshotWindow(self, include_frame: 'b', include_cursor: 'b', flash: 'b', filename: 's') -> 'bs':
        debug('ScreenshotWindow call:', filename)
        return self.Screenshot(include_cursor, flash, filename)

    @method()
    def ScreenshotArea(self, x: 'i', y: 'i', width: 'i', height: 'i', flash: 'b', filename: 's') -> 'bs':
        debug('ScreenshotArea call:', x, y, width, height, filename)
        try:
            os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
            cmd = ['grim', '-g', f'{x},{y} {width}x{height}', filename]
            subprocess.run(cmd, check=True)
            debug('Area screenshot saved:', filename)
            return [True, filename]
        except Exception as e:
            debug('ScreenshotArea error:', e)
            return [False, '']


class IdleMonitor(ServiceInterface):
    def __init__(self):
        super().__init__('org.gnome.Mutter.IdleMonitor')
        self.last_active = dt.datetime.now(dt.timezone.utc)
        self.monitor = None
        self.worker = None

    async def start(self):
        try:
            self.monitor = await asyncio.create_subprocess_exec(
                'swayidle', '-w',
                'timeout', '1', 'echo timeout',
                'resume', 'echo resume',
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            self.worker = asyncio.create_task(self.run())
            debug('swayidle started')
        except FileNotFoundError:
            debug('swayidle not found, idle tracking disabled')

    async def run(self):
        try:
            async for line in self.monitor.stdout:
                line = line.decode().strip()
                if line == 'resume':
                    self.last_active = dt.datetime.now(dt.timezone.utc)
        except Exception as e:
            debug('swayidle error:', e)

    @method()
    def GetIdletime(self) -> 't':
        delta = dt.datetime.now(dt.timezone.utc) - self.last_active
        return round(delta.total_seconds() * 1000)

    async def cleanup(self):
        if self.monitor and self.monitor.returncode is None:
            self.monitor.terminate()
            try:
                await asyncio.wait_for(self.monitor.wait(), timeout=2)
            except asyncio.TimeoutError:
                self.monitor.kill()


async def main():
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    debug('Connected to D-Bus')

    screenshot = ScreenshotInterface()
    bus.export('/org/gnome/Shell/Screenshot', screenshot)
    
    idle = IdleMonitor()
    await idle.start()
    bus.export('/org/gnome/Mutter/IdleMonitor/Core', idle)

    try:
        await bus.request_name('org.gnome.Shell.Screenshot')
        debug('Claimed org.gnome.Shell.Screenshot')
    except DBusError as e:
        debug(f'Failed to claim Screenshot: {e}')
        return

    if idle.worker:
        try:
            await bus.request_name('org.gnome.Mutter.IdleMonitor')
            debug('Claimed org.gnome.Mutter.IdleMonitor')
        except DBusError as e:
            debug(f'Warning: Failed to claim IdleMonitor: {e}')

    debug('Bridge ready!')

    try:
        await bus.wait_for_disconnect()
    finally:
        await idle.cleanup()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        debug('Stopped')