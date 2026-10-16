// SPDX-License-Identifier: GPL-2.0-or-later
// Terminal backend for doomgeneric; based on the platform interface examples.
#include "doomgeneric.h"
#include "doomkeys.h"
#include "doomstat.h"
#include "i_system.h"
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <sys/ioctl.h>
#include <time.h>
#include <string.h>
#include <signal.h>
#include <errno.h>

static int fd = -1, columns = 100, rows = 30, frames, inputs;
static struct termios original;
static int saved;
static uint32_t start, last_frame;
static uint32_t held[256];
static unsigned short queue[512];
static unsigned int qr, qw;
static volatile sig_atomic_t stopping;
static int escape_state;
static char sequence[32];
static size_t sequence_len;
static uint32_t escape_time;
extern int saveStringEnter;

static void release_keys(void) {
    /* Queue releases before menu entry so movement cannot remain held. */
    for (int k = 0; k < 256; k++) {
        if (held[k] && qw - qr < 512) queue[qw++ % 512] = k;
        held[k] = 0;
    }
}

uint32_t DG_GetTicksMs(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint32_t)(t.tv_sec * 1000 + t.tv_nsec / 1000000);
}
void DG_SleepMs(uint32_t ms) { usleep(ms * 1000); }
static void stop(int sig) { (void)sig; stopping = 1; }
static void send_bytes(const char *s, size_t n) {
    while (n && !stopping) {
        ssize_t k = write(fd, s, n);
        if (k > 0) { s += k; n -= k; }
        else if (errno != EINTR) break;
    }
}
static void cleanup(void) {
    if (fd >= 0) {
        if (saved) tcsetattr(fd, TCSANOW, &original);
        const char *s = "\033[0m\033[?25h\033[2J\033[H";
        ssize_t written = write(fd, s, strlen(s));
        (void)written;
        close(fd);
    }
    fprintf(stderr, "TERMINAL_DOOM frames=%d inputs=%d elapsed_ms=%u\n",
            frames, inputs, DG_GetTicksMs() - start);
}
void DG_Init(void) {
    const char *path = getenv("DOOM_TTY");
    fd = open(path ? path : "/dev/tty", O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) { perror("terminal"); exit(1); }
    if (tcgetattr(fd, &original) < 0) { perror("termios"); exit(1); }
    saved = 1;
    struct termios raw = original;
    cfmakeraw(&raw);
    raw.c_cc[VMIN] = 0;
    raw.c_cc[VTIME] = 0;
    tcsetattr(fd, TCSANOW, &raw);
    atexit(cleanup);
    signal(SIGTERM, stop); signal(SIGINT, stop); signal(SIGHUP, stop);
    struct winsize ws;
    if (ioctl(fd, TIOCGWINSZ, &ws) == 0) {
        if (ws.ws_col > 0 && ws.ws_col < columns) columns = ws.ws_col;
        if (ws.ws_row > 3 && ws.ws_row - 2 < rows) rows = ws.ws_row - 2;
    }
    start = DG_GetTicksMs();
    fprintf(stderr, "TERMINAL_DOOM started tty=%s size=%dx%d\n", path ? path : "/dev/tty", columns, rows);
    send_bytes("\033[2J\033[H\033[?25l", strlen("\033[2J\033[H\033[?25l"));
}
static void enqueue(int down, unsigned char key) {
    if (qw - qr < 512) queue[qw++ % 512] = (down << 8) | key;
}
static void keypress(unsigned char key) {
    /* Menus and text entry need a keydown for every typed character. */
    if (menuactive && held[key]) enqueue(0, key);
    if (!held[key] || menuactive) enqueue(1, key);
    held[key] = DG_GetTicksMs() + 180;
    inputs++;
}
static void special_key(unsigned char key) {
    if (key == KEY_ESCAPE || (key >= KEY_F1 && key <= KEY_F10)) release_keys();
    keypress(key);
}
static void escape_sequence(void) {
    unsigned char key = 0;
    if (sequence_len == 1) {
        switch (sequence[0]) {
            case 'A': key = KEY_UPARROW; break;
            case 'B': key = KEY_DOWNARROW; break;
            case 'C': key = KEY_RIGHTARROW; break;
            case 'D': key = KEY_LEFTARROW; break;
            case 'P': key = KEY_F1; break;
            case 'Q': key = KEY_F2; break;
            case 'R': key = KEY_F3; break;
            case 'S': key = KEY_F4; break;
        }
    } else if (sequence[sequence_len-1] == '~') {
        const int numbers[] = {11,12,13,14,15,17,18,19,20,21,23,24};
        const int keys[] = {KEY_F1,KEY_F2,KEY_F3,KEY_F4,KEY_F5,KEY_F6,
                            KEY_F7,KEY_F8,KEY_F9,KEY_F10,KEY_F11,KEY_F12};
        int number = atoi(sequence);
        for (int i = 0; i < 12; i++) if (number == numbers[i]) key = keys[i];
    }
    if (key) special_key(key);
}
static void input(void) {
    unsigned char c;
    for (int count = 0; count < 512 && read(fd, &c, 1) == 1; count++) {
        if (c == 3) { stopping = 1; return; }
        if (escape_state == 1 && (c == '[' || c == 'O')) {
            escape_state = 2; sequence_len = 0; continue;
        }
        if (escape_state >= 2) {
            /* Consume the whole CSI/SS3 sequence, including unknown reports. */
            if (sequence_len < sizeof(sequence)-1) sequence[sequence_len++] = c;
            else escape_state = 3;
            if (c >= 0x40 && c <= 0x7e) {
                sequence[sequence_len] = 0;
                if (escape_state == 2) escape_sequence();
                escape_state = 0;
            }
            continue;
        }
        if (escape_state == 1) {
            special_key(KEY_ESCAPE);
            escape_state = 0;
        }
        if (c == 27) { escape_state = 1; escape_time = DG_GetTicksMs(); continue; }
        if (c == '\n' || c == '\r') c = KEY_ENTER;
        if (c == 8 || c == 127) c = KEY_BACKSPACE;
        if (menuactive || gamestate != GS_LEVEL) { keypress(c); continue; }
        if (c == 'q') { stopping = 1; return; }
        switch(c) {
            case 'w': c = KEY_UPARROW; break;
            case 's': c = KEY_DOWNARROW; break;
            case 'a': c = KEY_LEFTARROW; break;
            case 'd': c = KEY_RIGHTARROW; break;
            case 'j': c = KEY_STRAFE_L; break;
            case 'l': c = KEY_STRAFE_R; break;
            case 'f': c = KEY_FIRE; break;
            case ' ': case 'e': c = KEY_USE; break;
            case 'r': c = KEY_RSHIFT; break;
            case '\n': c = KEY_ENTER; break;
        }
        keypress(c);
    }
    uint32_t now = DG_GetTicksMs();
    if (escape_state && now - escape_time >= 40) {
        if (escape_state == 1) special_key(KEY_ESCAPE);
        escape_state = 0;
    }
    for (int k = 0; k < 256; k++)
        if (held[k] && (int32_t)(now - held[k]) >= 0) {
            held[k] = 0; enqueue(0, k);
        }
}
int DG_GetKey(int *pressed, unsigned char *key) {
    input();
    if (qr == qw) return 0;
    unsigned short event = queue[qr++ % 512];
    *pressed = event >> 8; *key = event & 255;
    return 1;
}
static int color(uint32_t p) {
    int r = (p >> 16) & 255, g = (p >> 8) & 255, b = p & 255;
    return 16 + 36 * ((r * 5 + 127) / 255) + 6 * ((g * 5 + 127) / 255) + ((b * 5 + 127) / 255);
}
void DG_DrawFrame(void) {
    uint32_t now = DG_GetTicksMs();
    if (now - last_frame < 100) return;
    last_frame = now;
    char out[200000];
    size_t n = snprintf(out, sizeof(out), "\033[H");
    for (int y = 0; y < rows; y++) {
        int fg = -1, bg = -1;
        for (int x = 0; x < columns; x++) {
            int sx = x * DOOMGENERIC_RESX / columns;
            int sy = y * 2 * DOOMGENERIC_RESY / (rows * 2);
            int sy2 = (y * 2 + 1) * DOOMGENERIC_RESY / (rows * 2);
            int a = color(DG_ScreenBuffer[sy * DOOMGENERIC_RESX + sx]);
            int b = color(DG_ScreenBuffer[sy2 * DOOMGENERIC_RESX + sx]);
            if (a != fg) { n += snprintf(out+n, sizeof(out)-n, "\033[38;5;%dm", a); fg = a; }
            if (b != bg) { n += snprintf(out+n, sizeof(out)-n, "\033[48;5;%dm", b); bg = b; }
            memcpy(out+n, "▀", 3); n += 3;
        }
        n += snprintf(out+n, sizeof(out)-n, "\033[0m\033[K\r\n");
    }
    n += snprintf(out+n, sizeof(out)-n,
        "\033[0mWASD move | F fire | SPACE use | ESC menu | F2 save | F3 load | Ctrl-C return\033[K");
    send_bytes(out, n);
    frames++;
    if (frames % 100 == 0) fprintf(stderr, "TERMINAL_DOOM progress frames=%d inputs=%d\n", frames, inputs);
}
void DG_SetWindowTitle(const char *title) { (void)title; }
int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    doomgeneric_Create(argc, argv);
    const char *duration = getenv("DOOM_SECONDS");
    char *end;
    unsigned long seconds = duration ? strtoul(duration, &end, 10) : 0;
    if (duration && (!*duration || *duration == '-' || *end || seconds > UINT32_MAX / 1000)) {
        fprintf(stderr, "DOOM_SECONDS must be 0 (unlimited) or a positive duration <= 4294967\n");
        return 1;
    }
    while (!stopping && (!seconds || DG_GetTicksMs() - start < seconds * 1000)) {
        doomgeneric_Tick();
        static int last_episode = -1, last_map = -1, last_state = -1, last_menu = -1, last_save = -1;
        if (gameepisode != last_episode || gamemap != last_map || (int)gamestate != last_state
            || menuactive != last_menu || saveStringEnter != last_save) {
            mobj_t *player = gamestate == GS_LEVEL ? players[consoleplayer].mo : NULL;
            fprintf(stderr, "TERMINAL_STATE episode=%d map=%d state=%d menu=%d saving=%d x=%d y=%d ammo=%d\n",
                    gameepisode, gamemap, gamestate, menuactive, saveStringEnter,
                    player ? player->x : 0, player ? player->y : 0,
                    players[consoleplayer].ammo[am_clip]);
            last_episode = gameepisode; last_map = gamemap; last_state = gamestate;
            last_menu = menuactive; last_save = saveStringEnter;
        }
#ifdef TERMINAL_TEST
        extern void TerminalTest_Tick(int frames);
        TerminalTest_Tick(frames);
#endif
    }
    I_Quit();
    return 0;
}
