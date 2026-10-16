# Verification report — 2026-10-16

Tested on Linux x86-64, using separate 80×25 PTYs. The active user terminal was not suspended during this verification. The terminal handoff suite uses a real interactive Bash parent and a process named `codex` that stands in for the Codex UI; it does not run a second actual Codex client.

## Commands

```sh
python3 scripts/build.py --test
python3 tests/test_terminal.py
python3 tests/test_gameplay.py
```

## Results

```text
normal PASS S foreground restored; terminal settings restored
quit PASS S foreground restored; terminal settings restored
interrupt PASS S foreground restored; terminal settings restored
watchdog PASS S foreground restored; terminal settings restored
stalled PASS S foreground restored; terminal settings restored
unlimited PASS S foreground restored; terminal settings restored
controls PASS (terminal input changed player position and consumed ammunition)
menu/save/load PASS (ESC, SS3 F2, CSI F3/F10, repeated text, restart)
campaign PASS (36 map renders/save/loads, secret routes, 4 text/art finales)
```

## Campaign coverage

| Episode | Maps rendered, saved and loaded | Secret route | Finale |
| --- | --- | --- | --- |
| 1 | E1M1–E1M9 | M3 → M9 → M4 | Text + artwork |
| 2 | E2M1–E2M9 | M5 → M9 → M6 | Text + artwork |
| 3 | E3M1–E3M9 | M6 → M9 → M7 | Text + scrolling artwork through END6 |
| 4 | E4M1–E4M9 | M2 → M9 → M3 | Text + artwork |

The test-only driver invokes the engine's real `G_ExitLevel` / `G_SecretExitLevel` functions, then advances the actual intermission/finale state machines. Each map is rendered before its engine save/load round trip; the next map number is checked against the expected route. Each episode's text and artwork are rendered before advancing to the next episode. This driver is compiled only into `doom-terminal-test`, not the playable `doom-terminal` binary.

Separately, terminal key events change the player's position and consume ammunition in the production binary. Saving through F2 preserves repeated movement-key letters and Q in the save name. A fresh production process loads that save back into the same episode and map, and F3 and F10 exercise engine menu paths.

The unlimited-launcher test remains running beyond the old 30-second default before quitting with Q. Watchdog tests cover both an exited launcher and a launcher frozen by SIGSTOP, while checking terminal ownership and exact termios restoration.

## Fixes found by verification

The original 6 MiB zone heap ran out when loading the map after E4M6. The patched default is 64 MiB; the complete campaign then passed. Vanilla's save-size cap is disabled by default for Freedoom's larger maps. The engine's normal quit path now exits even with `show_endoom 0`.

## Scope

This is automated coverage of input, persistence, scene loading, transitions and ending presentation. It is **not a human playthrough**, and it does not prove every route is reachable by walking, every boss encounter is completable, or every camera view is free of vanilla renderer limits. It also does not certify all SSH clients or Codex versions. No sound output is implemented.
