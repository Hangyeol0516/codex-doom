#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fetch pinned upstream sources and data, then build the terminal backend."""
import hashlib
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--test', action='store_true', help='also build the progression test driver')
args = parser.parse_args()
REVISION = "e257a09527062bfb986b6e5e0780839b6cbd5b71"
URL = "https://github.com/freedoom/freedoom/releases/download/v0.13.0/freedoom-0.13.0.zip"
SHA256 = "3f9b264f3e3ce503b4fb7f6bdcb1f419d93c7b546f4df3e874dd878db9688f59"

def run(*args, cwd=ROOT):
    subprocess.run(args, cwd=cwd, check=True)

engine = ROOT / "engine"
if not engine.exists():
    run("git", "clone", "https://github.com/ozkl/doomgeneric.git", str(engine))
run("git", "checkout", "--detach", REVISION, cwd=engine)
source = engine / "doomgeneric"
# doomgeneric leaves exit(0) under ORIGCODE in I_Quit; make menu quits
# terminate even when show_endoom is disabled in the saved configuration.
system = source / 'i_system.c'
original_system = subprocess.check_output(['git', 'show', REVISION + ':doomgeneric/i_system.c'], cwd=engine).decode()
original_quit = '#if ORIGCODE\n    SDL_Quit();\n\n    exit(0);\n#endif'
assert original_quit in original_system
assert '#define DEFAULT_RAM 6 ' in original_system
patched_system = original_system.replace(original_quit, '#if ORIGCODE\n    SDL_Quit();\n#endif\n    exit(0);')
# Later Freedoom maps exhaust doomgeneric's original 6 MiB zone heap.
# The engine's -mb argument can still override the new default.
system.write_text(patched_system.replace('#define DEFAULT_RAM 6 ', '#define DEFAULT_RAM 64 '))
game = source / 'g_game.c'
original_game = subprocess.check_output(['git', 'show', REVISION + ':doomgeneric/g_game.c'], cwd=engine).decode()
original_limit = 'int             vanilla_savegame_limit = 1;'
assert original_limit in original_game
game.write_text(original_game.replace(original_limit, 'int             vanilla_savegame_limit = 0;'))
shutil.copyfile(ROOT / "src/doomgeneric_terminal.c", source / "doomgeneric_terminal.c")
makefile = (source / "Makefile").read_text()
makefile = makefile.replace("doomgeneric_xlib.o", "doomgeneric_terminal.o")
makefile = makefile.replace("OUTPUT=doomgeneric", "OUTPUT=doom-terminal").replace("-lX11", "")
makefile = makefile.replace('OBJS +=', 'ifdef TERMINAL_TEST\nSRC_DOOM += progression_driver.o\nendif\nOBJS +=', 1)
(source / "Makefile.terminal").write_text(makefile)
archive = ROOT / "freedoom-0.13.0.zip"
if not archive.exists():
    temporary = archive.with_suffix(".zip.part")
    try:
        with urllib.request.urlopen(URL, timeout=90) as response, temporary.open("wb") as out:
            shutil.copyfileobj(response, out)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
    raise SystemExit("Freedoom archive checksum mismatch; remove the archive and retry")
with zipfile.ZipFile(archive) as package:
    member = next(n for n in package.namelist() if n.endswith("/freedoom1.wad"))
    (ROOT / "freedoom1.wad").write_bytes(package.read(member))
    for member in package.namelist():
        if Path(member).name.lower() in ("copying", "copying.txt", "license", "license.txt"):
            (ROOT / "engine/FREEDOOM-LICENSE.txt").write_bytes(package.read(member))
flags = "-O2 -Wall -DNORMALUNIX -DLINUX -DSNDSERV -D_DEFAULT_SOURCE -DDOOMGENERIC_RESX=320 -DDOOMGENERIC_RESY=200"
run("make", "-f", "Makefile.terminal", "-j", str(min(os.cpu_count() or 1, 4)),
    "CC=gcc", "CFLAGS=" + flags, cwd=source)
print("Built:", source / "doom-terminal")
if args.test:
    shutil.copyfile(ROOT / 'tests/progression_driver.c', source / 'progression_driver.c')
    run('make', '-f', 'Makefile.terminal', '-j', str(min(os.cpu_count() or 1, 4)),
        'CC=gcc', 'CFLAGS=' + flags + ' -DTERMINAL_TEST', 'TERMINAL_TEST=1',
        'OBJDIR=build-test', 'OUTPUT=doom-terminal-test', cwd=source)
