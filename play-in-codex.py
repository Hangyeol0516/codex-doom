#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Give Doom the Codex terminal with a stopped parent shell and rescue process."""
import argparse
import os
from pathlib import Path
import select
import signal
import subprocess
import termios
import time

ROOT = Path(__file__).resolve().parent
OFF = b"".join(f"\x1b[?{m}l".encode() for m in (9,1000,1001,1002,1003,1004,1005,1006,1015,1016,2004))
ON = b"".join(f"\x1b[?{m}h".encode() for m in (1000,1002,1003,1006,2004))

def stat(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()
    return dict(state=fields[0], parent=int(fields[1]), group=int(fields[2]), foreground=int(fields[5]))

def wait_state(pid, stopped):
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        if (stat(pid)["state"] in ("T", "t")) == stopped:
            return
        time.sleep(.005)
    raise RuntimeError(f"Process {pid} did not reach expected state")

def play(pid, seconds):
    info = stat(pid)
    shell_pid = info["parent"]
    if Path(f"/proc/{pid}/comm").read_text().strip() != "codex":
        raise RuntimeError("Target is not Codex")
    if Path(f"/proc/{shell_pid}/comm").read_text().strip() != "bash":
        raise RuntimeError("Expected a Bash parent")
    if info["foreground"] != info["group"] or info["state"] in ("T", "t"):
        raise RuntimeError("Codex must already be running in the foreground")
    tty = os.readlink(f"/proc/{pid}/fd/0")
    if not tty.startswith("/dev/pts/"):
        raise RuntimeError("Expected a terminal")
    fd = os.open(tty, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    original = termios.tcgetattr(fd)
    child = None
    def output(data):
        try: os.write(fd, data)
        except BlockingIOError: pass
    def restore():
        # Bash stays stopped while residual mouse/input reports are discarded.
        output(OFF + b"\x1b[0m\x1b[?25h\x1b[2J\x1b[H")
        termios.tcflush(fd, termios.TCIFLUSH)
        termios.tcsetattr(fd, termios.TCSANOW, original)
        os.kill(pid, signal.SIGCONT)
        wait_state(pid, False)
        os.kill(pid, signal.SIGWINCH)
        time.sleep(.1)
        os.kill(shell_pid, signal.SIGCONT)
        time.sleep(.1)
        current = stat(pid)
        if current["foreground"] != info["group"] or current["state"] in ("T", "t"):
            # Keep reports disabled if the CLI failed to regain the terminal.
            output(b"\r\nType fg to return to Codex.\r\n")
            raise RuntimeError("Codex foreground restoration failed")
        output(ON)
    # The watchdog exists before either foreground process is suspended.
    read_end, write_end = os.pipe()
    watchdog = os.fork()
    if watchdog == 0:
        os.close(write_end)
        game_pid = None
        deadline = time.monotonic() + seconds + 8
        buffer = b""
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([read_end], [], [], max(0, deadline-time.monotonic()))
                if not ready: break
                chunk = os.read(read_end, 128)
                if not chunk: break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line == b"done": os._exit(0)
                    game_pid = int(line)
            if game_pid:
                try: os.killpg(game_pid, signal.SIGKILL)
                except ProcessLookupError: pass
            try: restore()
            finally: os.kill(shell_pid, signal.SIGCONT)
        finally:
            os._exit(0)
    os.close(read_end)
    def interrupted(signum, frame):
        raise InterruptedError(f"signal {signum}")
    old_handlers = {s: signal.signal(s, interrupted) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        os.kill(shell_pid, signal.SIGSTOP)
        wait_state(shell_pid, True)
        # Freezing Bash first prevents it from consuming terminal reports or
        # taking the foreground when its Codex child stops.
        os.kill(pid, signal.SIGSTOP)
        wait_state(pid, True)
        output(OFF)
        termios.tcflush(fd, termios.TCIFLUSH)
        env = dict(os.environ, DOOM_TTY=tty, DOOM_SECONDS=str(seconds))
        with (ROOT / "last-run.log").open("wb") as log:
            child = subprocess.Popen([
                str(ROOT / "engine/doomgeneric/doom-terminal"),
                "-iwad", str(ROOT / "freedoom1.wad"),
                "-warp", "1", "1", "-skill", "2", "-nosound",
                "-config", str(ROOT / "doom.cfg"),
            ], cwd=ROOT, env=env, stdout=log, stderr=log, start_new_session=True)
            os.write(write_end, f"{child.pid}\n".encode())
            try: child.wait(timeout=seconds+3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                raise RuntimeError("Doom exceeded its deadline")
    finally:
        try:
            if child is not None and child.poll() is None:
                child.kill()
                child.wait()
            restore()
        finally:
            os.kill(shell_pid, signal.SIGCONT)
            os.write(write_end, b"done\n")
            os.close(write_end)
            os.waitpid(watchdog, 0)
            os.close(fd)
            for s, handler in old_handlers.items(): signal.signal(s, handler)
    if child.returncode:
        raise RuntimeError(f"Doom exited with {child.returncode}")
    print(f"Doom finished; Codex and Bash restored on {tty}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--seconds", type=int, default=30)
    args = parser.parse_args()
    play(args.pid, max(1, min(args.seconds, 300)))
