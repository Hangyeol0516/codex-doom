# codex-doom

Run the Doom engine in the **same terminal window as Codex CLI**, using ANSI colors and half-block characters. This is an experimental Linux terminal backend and launcher, built during a conversation with Codex.

The engine is [doomgeneric](https://github.com/ozkl/doomgeneric). Game assets come from [Freedoom](https://freedoom.github.io/), rather than a commercial Doom WAD. This project does not modify the Codex executable.

## 빠른 시작

Linux, Python 3, Git, GCC, Make와 UTF-8·256색 터미널이 필요합니다. 현재 launcher는 Bash에서 실행 중인 Codex CLI만 지원합니다.

```sh
git clone https://github.com/Hangyeol0516/codex-doom.git
cd codex-doom
python3 scripts/build.py
python3 tests/test_terminal.py
```

빌드는 고정된 doomgeneric 커밋과 Freedoom 0.13.0을 내려받습니다. Freedoom ZIP의 SHA-256도 검사합니다. 소스·바이너리·데이터는 로컬에서 생성되며 Git에 포함하지 않습니다.

### Codex와 같은 창에서 실행

실행 중인 Codex에게 이 레포의 launcher를 실행하도록 요청하거나, 같은 머신의 별도 셸에서 실행합니다. Codex CLI가 있는 터미널에서 직접 명령을 실행하려고 Codex를 먼저 중단하면 launcher의 사전 검사에 실패합니다.

```sh
# TTY가 있는 codex 프로세스의 PID를 확인합니다.
ps -u "$USER" -o pid,tty,comm

# 예: PID가 12345인 경우. 기본 실행 시간은 30초입니다.
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
| Q / Ctrl-C | 게임 종료, Codex로 복귀 |

첫 맵으로 바로 진입합니다. 소리는 없습니다. 터미널에는 키를 놓는 이벤트가 없으므로 마지막 입력 후 180ms가 지나면 키를 놓은 것으로 처리합니다. 키를 오래 누를 때의 반응은 터미널의 반복 입력 설정에 영향을 받습니다.

### 일반 터미널에서 실행

Codex를 정지시키지 않고 전용 터미널에서 backend만 실행할 수도 있습니다.

```sh
DOOM_SECONDS=30 engine/doomgeneric/doom-terminal \
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

Launcher가 종료되거나 제한 시간을 넘기면 watchdog도 같은 복구를 시도합니다. 마우스 모드는 Codex에서 쓰는 일반적인 설정으로 복원하며, 원래 escape 기반 터미널 모드를 모두 조회·저장하는 구현은 아닙니다. 이 launcher는 임의의 셸이나 다른 TUI를 위한 범용 터미널 인계 도구가 아닙니다.

문제가 생겨 Bash 프롬프트로 돌아온 경우 `fg`로 Codex를 재개할 수 있습니다. 입력 상태가 이상하면 별도 SSH 세션에서 해당 TTY에 `stty -F /dev/pts/N sane`을 적용할 수 있습니다. `N`은 실제 대상 터미널 번호로 바꿔야 합니다.

## 검증 결과와 한계

별도 PTY에 실제 interactive Bash와 Codex 역할의 프로세스를 구성하고, Doom backend까지 실행해 다음을 검사했습니다.

- 시간 제한 종료와 Q 종료
- Launcher의 SIGTERM 중단과 SIGKILL 후 watchdog 복구
- 종료 후 CLI가 foreground에 있고 Bash가 정지 상태로 남지 않는지
- 원래 termios가 정확히 복원되는지
- 이동·발사 입력 처리와 Q의 조기 종료

실제 Codex CLI 터미널에서는 최종 시도에 **30초 동안 263프레임을 출력하고 정상 복귀**했습니다. 그 실행의 입력 기록은 **0건**이므로 실제 사용자 키보드로 플레이가 됐다는 주장은 하지 않습니다. 키 입력 처리는 별도 PTY 테스트에서 확인했습니다. 터미널·SSH 클라이언트·Codex 버전에 따라 추가 검증이 필요합니다.

## 파일

- `src/doomgeneric_terminal.c`: 화면 출력, 키 입력, 시간 제한
- `play-in-codex.py`: Codex/Bash 일시 정지와 복구
- `scripts/build.py`: 고정된 upstream 소스와 Freedoom 데이터로 빌드
- `tests/test_terminal.py`: Bash job control과 터미널 복구 통합 테스트

## 라이선스와 출처

이 프로젝트 코드는 GPL-2.0-or-later로 제공합니다. [LICENSE](LICENSE)를 참고하세요. doomgeneric의 upstream 라이선스와 저작권 고지도 다운로드된 `engine/`에 유지됩니다. Freedoom 데이터는 별도 BSD 계열 라이선스를 따르며, 라이선스 문서도 빌드 시 함께 추출합니다.

- doomgeneric: [`e257a09527062bfb986b6e5e0780839b6cbd5b71`](https://github.com/ozkl/doomgeneric/tree/e257a09527062bfb986b6e5e0780839b6cbd5b71)
- Freedoom: [0.13.0 release](https://github.com/freedoom/freedoom/releases/tag/v0.13.0)
