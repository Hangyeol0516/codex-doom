# codex-doom

Run the Doom engine in the **same terminal window as Codex CLI**, using ANSI colors and half-block characters. This is an experimental Linux terminal backend and launcher, built during a conversation with Codex.

The engine is [doomgeneric](https://github.com/ozkl/doomgeneric). Game assets come from [Freedoom](https://freedoom.github.io/), rather than a commercial Doom WAD. This project does not modify the Codex executable.

## 빠른 시작

Linux, Python 3, Git, GCC, Make와 UTF-8·256색 터미널이 필요합니다. 현재 launcher는 Bash에서 실행 중인 Codex CLI만 지원합니다.

```sh
git clone https://github.com/Hangyeol0516/codex-doom.git
cd codex-doom
python3 scripts/build.py --test
python3 tests/test_terminal.py
python3 tests/test_gameplay.py
```

빌드는 고정된 doomgeneric 커밋과 Freedoom 0.13.0을 내려받습니다. Freedoom ZIP의 SHA-256도 검사합니다. 소스·바이너리·데이터는 로컬에서 생성되며 Git에 포함하지 않습니다.

### Codex와 같은 창에서 실행

실행 중인 Codex에게 이 레포의 launcher를 실행하도록 요청하거나, 같은 머신의 별도 셸에서 실행합니다. Codex CLI가 있는 터미널에서 직접 명령을 실행하려고 Codex를 먼저 중단하면 launcher의 사전 검사에 실패합니다.

```sh
# TTY가 있는 codex 프로세스의 PID를 확인합니다.
ps -u "$USER" -o pid,tty,comm

# 기본: 시간 제한 없이 첫 에피소드부터 플레이. Ctrl-C로 복귀합니다.
python3 play-in-codex.py --pid 12345

# 4번째 에피소드, 첫 맵, 보통 난이도에서 시작
python3 play-in-codex.py --pid 12345 --episode 4 --map 1 --skill 3

# 저장 슬롯 0에서 이어하기 (슬롯 번호는 0–5)
python3 play-in-codex.py --pid 12345 --load-slot 0

# 짧은 시연이 필요할 때만 시간 제한 지정 (300초 상한 없음)
python3 play-in-codex.py --pid 12345 --seconds 30
```

Launcher는 대상이 `codex`인지, 부모가 Bash인지, Codex가 터미널의 foreground인지 확인합니다. 정확한 PID를 지정해야 합니다.

| 키 | 동작 |
| --- | --- |
| W / S, ↑ / ↓ | 전진 / 후진 |
| A / D, ← / → | 좌우 회전 |
| J / L | 좌우로 옆걸음 |
| F | 발사 |
| Space / E | 문 열기·사용 |
| 1–7 | 무기 선택 |
| R | 달리기 (W와 함께 누르기) |
| Esc | 메뉴 열기 / 닫기 |
| 방향키 / Enter / Backspace | 메뉴 선택 / 확인 / 뒤로 |
| F2 / F3 | 저장 / 불러오기 |
| F6 / F9 | 빠른 저장 / 빠른 불러오기 |
| Q | 플레이 중 종료, Codex로 복귀 (메뉴에서는 문자 입력) |
| Ctrl-C | 메뉴·엔딩을 포함해 언제든 종료, Codex로 복귀 |

기본은 첫 맵으로 바로 진입하며, **시간 제한은 없습니다** (`--seconds 0`도 동일). 소리는 없습니다. 에피소드 1–4는 각각 독립된 캠페인입니다. 각 에피소드의 M8에서 엔딩으로 진행하고, M9는 비밀 맵입니다. 다음 에피소드는 Esc → New Game으로 선택하거나 launcher의 `--episode`로 시작합니다. Freedoom Phase 1의 36개 맵을 사용하며 Freedoom Phase 2는 이 launcher의 대상이 아닙니다.

저장은 레포 디렉터리의 `.savegame/doomsav0.dsg`–`doomsav5.dsg`에, 설정은 `doom.cfg`에 보관됩니다. F2로 슬롯을 선택하고 이름을 입력해 저장한 뒤 F3 또는 `--load-slot`으로 이어갈 수 있습니다. **저장하지 않고 Q나 Ctrl-C로 종료하면 자동 저장하지 않습니다.** 저장 이름 입력 중에는 WASD와 Q도 글자로 처리하며, 연속된 같은 문자도 입력할 수 있습니다. 기존 `doom.cfg`에 `vanilla_savegame_limit 1`이 있다면 `0`으로 바꿔야 큰 맵을 저장할 수 있습니다.

터미널에는 키를 놓는 이벤트가 없으므로 마지막 입력 후 180ms가 지나면 키를 놓은 것으로 처리합니다. 키를 오래 누를 때의 반응은 터미널의 반복 입력 설정에 영향을 받습니다.

### 일반 터미널에서 실행

Codex를 정지시키지 않고 전용 터미널에서 backend만 실행할 수도 있습니다.

```sh
DOOM_SECONDS=0 engine/doomgeneric/doom-terminal \
  -iwad "$PWD/freedoom1.wad" -warp 1 1 -nosound
```

## 화면을 어떻게 그리나?

Doom이 렌더링한 320×200 RGB 화면은 `DG_ScreenBuffer`에 들어갑니다. Backend는 최대 100×60으로 샘플링하고, RGB를 ANSI 256색 팔레트로 변환합니다. 실제 출력은 최대 **100열×30행**입니다. 창이 작으면 출력 크기도 줄어듭니다.

`▀` 문자의 윗부분은 글자색, 아랫부분은 배경색입니다. 따라서 위아래 두 픽셀을 터미널 한 칸에 표현할 수 있습니다.

```text
위 픽셀 색 → ANSI foreground color ┐
                                   ├→ ▀ 한 글자 = 위아래 두 픽셀
아래 픽셀 색 → ANSI background color┘
```

예를 들어 위가 빨강, 아래가 파랑이면 다음 문자열로 한 칸을 그립니다. 실제 renderer는 기본 8색 대신 256색 escape를 사용합니다.

```python
"\x1b[31m\x1b[44m▀"
```

매 프레임 커서를 맨 위로 옮겨 화면을 덮어쓰며, 출력 빈도는 최대 약 10fps입니다. 터미널 파일은 nonblocking으로 열어 출력 대기 때문에 종료가 막히지 않게 합니다. 느린 연결에서는 프레임 일부가 생략되거나 깨져 보일 수 있습니다.

## 터미널 인계와 복구

처음에는 Codex만 정지시켰습니다. 그러자 Bash가 foreground를 가져갔고, 기존 마우스 보고 escape가 셸의 명령으로 해석되어 `명령을 찾을 수 없습니다`가 반복됐습니다. 그 시도는 플레이에 실패했습니다.

현재 launcher는 다음 순서로 동작합니다.

1. 원래 terminal 설정을 저장하고, 독립 watchdog을 먼저 시작합니다.
2. 부모 Bash를 정지시킨 뒤 Codex를 정지시킵니다. Bash가 foreground를 가져갈 수 없도록 합니다.
3. 마우스·포커스·붙여넣기 보고를 끄고 남은 입력을 비운 뒤 게임을 실행합니다.
4. 종료 시 게임을 정리하고, 입력을 비우고, 원래 termios를 복원합니다.
5. Codex를 먼저 재개하고 Bash를 재개한 뒤 foreground가 유지됐는지 확인합니다. 확인 후 Codex용 마우스·붙여넣기 모드를 다시 켭니다.

Launcher는 실행 중 heartbeat를 보내고, watchdog은 그 heartbeat가 8초간 끊기거나 pipe가 닫히면 게임을 종료하고 복구합니다. 게임의 전체 플레이 시간과 watchdog의 생존 확인 시간은 별개이므로 무제한 플레이 중에도 복구 기능이 유지됩니다. `--seconds`를 지정했다면 그 시간 제한도 적용됩니다. 마우스 모드는 Codex에서 쓰는 일반적인 설정으로 복원하며, 원래 escape 기반 터미널 모드를 모두 조회·저장하는 구현은 아닙니다. 이 launcher는 임의의 셸이나 다른 TUI를 위한 범용 터미널 인계 도구가 아닙니다.

문제가 생겨 Bash 프롬프트로 돌아온 경우 `fg`로 Codex를 재개할 수 있습니다. 입력 상태가 이상하면 별도 SSH 세션에서 해당 TTY에 `stty -F /dev/pts/N sane`을 적용할 수 있습니다. `N`은 실제 대상 터미널 번호로 바꿔야 합니다.

## 검증 결과와 한계

### 플레이를 막던 문제 수정

- 30초 자동 종료와 300초 상한을 없앴습니다. 기본 무제한이며 양의 `--seconds`로 제한을 선택할 수 있습니다.
- 단독 Esc, CSI/SS3 방향키·F1–F12, Enter·Backspace를 처리합니다. 게임 이동 키 변환은 메뉴·저장 이름 입력에 적용하지 않습니다.
- 메뉴 진입 시 이동 키를 놓아 메뉴를 닫은 뒤에도 이동이 계속되는 문제를 방지합니다.
- 종료 시 엔진의 정상 종료 루틴으로 설정을 저장합니다. `show_endoom 0`일 때 메뉴 종료가 실제 종료하지 않던 upstream 코드도 수정합니다.
- **기본 zone heap을 6MiB에서 64MiB로 늘렸습니다.** 이전 값으로 전체 검사를 돌리면 E4M6 다음 맵을 불러올 때 메모리가 부족해 종료됐습니다. 엔진의 `-mb` 인수로 변경할 수 있습니다.
- 큰 맵을 저장할 수 있도록 vanilla 저장 용량 제한의 기본값을 해제했습니다. [Freedoom 0.13.0 릴리스 설명](https://freedoom.github.io/#freedoom-0.13.0)에도 기존 저장 용량 제한 문제가 명시돼 있습니다.

### 실행 검증

[검증 기록과 범위](docs/verification.md)에 통과 결과와 에피소드별 경로를 정리했습니다.

사용자가 쓰는 실제 Codex 창을 빼앗지 않고, 별도 PTY에서 실제 backend와 interactive Bash를 실행해 검사합니다.

`tests/test_terminal.py`:

- 시간 제한 종료, 기본 무제한 실행에서 Q 종료
- Launcher의 SIGTERM, SIGKILL, SIGSTOP 이후 복구
- 기본 무제한 세션이 기존 30초 제한을 넘겨 실행되고 Q로 종료되는지
- 종료 후 CLI가 foreground에 있고 Bash가 멈춰 있지 않은지
- 원래 termios가 정확히 복원되는지

`tests/test_gameplay.py`:

- 터미널의 이동·발사 입력으로 플레이어 좌표와 탄약이 실제로 변하는지
- 단독 Esc, 분할 수신한 SS3 F2, CSI F3/F10, 저장 이름의 반복 문자 처리
- 파일로 저장한 게임을 새 프로세스에서 불러와 같은 에피소드·맵으로 복원하는지
- **비밀 경로를 포함한 36개 맵의 화면 출력·저장·불러오기**
- 실제 exit → intermission → 다음 맵 전환과 **4개 에피소드의 엔딩 텍스트·그림 출력** (에피소드 3의 마지막 END6 장면 포함)

캠페인 테스트는 `--test` 빌드에만 포함되는 `tests/progression_driver.c`가 엔진의 exit 함수를 호출하고 intermission/finale 타이머를 빠르게 진행시킵니다. 일반 게임 바이너리에는 이 코드가 포함되지 않습니다. 맵 로딩·저장·불러오기·전환·엔딩을 자동 검증하며, 사람이 길을 찾아 이동하거나 보스를 처치하는 전 맵 수동 완주는 아닙니다. 따라서 모든 경로의 도달 가능성과 모든 시점의 렌더링·전투 상황까지 검증했다고 주장하지 않습니다.

터미널은 약 10fps이며 키를 놓는 동작을 추정합니다. 일반 그래픽 창보다 조작이 불편하고, SSH 클라이언트·터미널·Codex 버전에 따라 차이가 있습니다. 원래 실제 Codex 창에서의 실험은 30초 동안 263프레임을 출력하고 복귀했으며, 그때 사용자 키 입력은 기록되지 않았습니다. 이후 입력·게임 진행 검증은 위 PTY 테스트로 수행했습니다.

## 파일

- `src/doomgeneric_terminal.c`: 화면 출력, 키 입력, 시간 제한
- `play-in-codex.py`: Codex/Bash 일시 정지와 복구
- `scripts/build.py`: 고정된 upstream 소스와 Freedoom 데이터로 빌드
- `tests/test_terminal.py`: Bash job control, 무제한 실행, 터미널 복구 통합 테스트
- `tests/test_gameplay.py`: 실제 입력·저장·불러오기·전체 맵·엔딩 검증
- `tests/progression_driver.c`: 테스트 빌드 전용 캠페인 진행 드라이버

## 라이선스와 출처

이 프로젝트 코드는 GPL-2.0-or-later로 제공합니다. [LICENSE](LICENSE)를 참고하세요. doomgeneric의 upstream 라이선스와 저작권 고지도 다운로드된 `engine/`에 유지됩니다. Freedoom 데이터는 별도 BSD 계열 라이선스를 따르며, 라이선스 문서도 빌드 시 함께 추출합니다.

- doomgeneric: [`e257a09527062bfb986b6e5e0780839b6cbd5b71`](https://github.com/ozkl/doomgeneric/tree/e257a09527062bfb986b6e5e0780839b6cbd5b71)
- Freedoom: [0.13.0 release](https://github.com/freedoom/freedoom/releases/tag/v0.13.0)
