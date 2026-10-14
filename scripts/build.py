#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fetch pinned upstream sources and data, then build the terminal backend."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
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
shutil.copyfile(ROOT / "src/doomgeneric_terminal.c", source / "doomgeneric_terminal.c")
makefile = (source / "Makefile").read_text()
makefile = makefile.replace("doomgeneric_xlib.o", "doomgeneric_terminal.o")
makefile = makefile.replace("OUTPUT=doomgeneric", "OUTPUT=doom-terminal").replace("-lX11", "")
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
