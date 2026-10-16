#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise real backend input, persistence, and a test-only campaign driver."""
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import struct
import subprocess
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]


class Game:
    def __init__(self, directory, *, test=False, extra=(), seconds=0):
        self.directory = Path(directory)
        self.master, self.slave = pty.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 25, 80, 0, 0))
        self.original = termios.tcgetattr(self.slave)
        self.log_path = self.directory / ('campaign.log' if test else 'game.log')
        self.log = self.log_path.open('wb')
        config = self.directory / 'game.cfg'
        if not config.exists():
            config.write_text('show_endoom 0\n')
        executable = 'doom-terminal-test' if test else 'doom-terminal'
        self.process = subprocess.Popen([
            str(ROOT / 'engine/doomgeneric' / executable),
            '-iwad', str(ROOT / 'freedoom1.wad'), '-nosound',
            '-config', str(config), *extra,
        ], cwd=directory, env=dict(os.environ, DOOM_TTY=os.ttyname(self.slave),
                                  DOOM_SECONDS=str(seconds)), stdout=self.log, stderr=self.log)

    def text(self):
        return self.log_path.read_text(errors='replace')

    def pump(self, duration=.05):
        if select.select([self.master], [], [], duration)[0]:
            os.read(self.master, 65536)

    def wait(self, condition, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.pump()
            if condition():
                return
            if self.process.poll() is not None:
                raise AssertionError(self.text())
        raise AssertionError('Timeout:\n' + self.text()[-4000:])

    def fields(self):
        lines = re.findall(r'TERMINAL_STATE ([^\n]+)', self.text())
        if not lines:
            return {}
        return dict(re.findall(r'(\w+)=(-?\d+)', lines[-1]))

    def state(self, **expected):
        fields = self.fields()
        return all(int(fields.get(k, -999)) == v for k, v in expected.items())

    def send(self, data):
        os.write(self.master, data)

    def finish(self, timeout=5):
        self.wait(lambda: self.process.poll() is not None, timeout)
        assert self.process.returncode == 0, self.text()
        assert termios.tcgetattr(self.slave) == self.original

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()
        self.log.close()
        os.close(self.master)
        os.close(self.slave)


def menu_and_save():
    with tempfile.TemporaryDirectory() as directory:
        game = Game(directory, extra=('-warp', '2', '3'))
        try:
            game.wait(lambda: game.state(episode=2, map=3, menu=0))
            game.send(b'\x1b')  # lone ESC must open the menu after its timeout
            game.wait(lambda: game.state(menu=1))
            game.send(b'\x1b')
            game.wait(lambda: game.state(menu=0))
            # Split an SS3 function-key sequence across reads.
            for byte in (b'\x1b', b'O', b'Q'):
                game.send(byte)
                game.pump(.01)
            game.wait(lambda: game.state(menu=1, saving=0))
            game.send(b'\r')
            game.wait(lambda: game.state(saving=1))
            game.send(b'wasdqq')  # mapped movement keys and repeated q are text here
            game.pump(.1)
            game.send(b'\r')
            save = Path(directory) / '.savegame/doomsav0.dsg'
            game.wait(lambda: save.exists() and save.stat().st_size > 43)
            assert save.read_bytes()[:24].rstrip(b'\0') == b'WASDQQ', save.read_bytes()[:24]
            game.send(b'q')
            game.finish()
        finally:
            game.close()
        # Load across process restarts, not merely from in-memory state.
        loaded = Game(directory, extra=('-loadgame', '0'))
        try:
            loaded.wait(lambda: loaded.state(episode=2, map=3, menu=0))
            loaded.send(b'\x1b[13~')  # CSI F3
            loaded.wait(lambda: loaded.state(menu=1))
            loaded.send(b'\r')
            loaded.wait(lambda: loaded.state(menu=0))
            loaded.send(b'\x1b[21~')  # F10 and the engine's normal quit path
            loaded.wait(lambda: loaded.state(menu=1))
            loaded.send(b'y')
            loaded.finish()
        finally:
            loaded.close()
    print('menu/save/load PASS (ESC, SS3 F2, CSI F3/F10, repeated text, restart)', flush=True)


def controls():
    with tempfile.TemporaryDirectory() as directory:
        game = Game(directory, extra=('-warp', '1', '1'))
        try:
            game.wait(lambda: game.state(state=0, menu=0))
            before = game.fields()
            for _ in range(12):
                game.send(b'wf')
                game.pump(.05)
            game.send(b'\x1b')
            game.wait(lambda: game.state(menu=1))
            after = game.fields()
            assert (before['x'], before['y']) != (after['x'], after['y']), (before, after)
            assert int(after['ammo']) < int(before['ammo']), (before, after)
            game.send(b'\x03')
            game.finish()
        finally:
            game.close()
    print('controls PASS (terminal input changed player position and consumed ammunition)', flush=True)


def campaign():
    with tempfile.TemporaryDirectory() as directory:
        game = Game(directory, test=True, extra=('-warp', '1', '1'), seconds=180)
        try:
            game.wait(lambda: game.process.poll() is not None, timeout=180)
            assert game.process.returncode == 0, game.text()
            log = game.text()
            maps = re.findall(r'PROGRESSION MAP E(\d)M(\d) rendered saved loaded', log)
            assert set(maps) == {(str(e), str(m)) for e in range(1, 5) for m in range(1, 10)}, log
            assert len(maps) == 36 and 'PROGRESSION PASS maps=36 endings=4' in log, log
            assert len(re.findall(r'PROGRESSION TEXT E\d rendered', log)) == 4
            assert len(re.findall(r'PROGRESSION END E\d rendered', log)) == 4
            assert termios.tcgetattr(game.slave) == game.original
        finally:
            game.close()
    print('campaign PASS (36 map renders/save/loads, secret routes, 4 text/art finales)', flush=True)


if __name__ == '__main__':
    controls()
    menu_and_save()
    campaign()
