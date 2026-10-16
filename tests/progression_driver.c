// SPDX-License-Identifier: GPL-2.0-or-later
// Test-only driver: invokes real exit/intermission/finale paths without
// navigating geometry or fighting enemies. Never linked into the game build.
#include "doomgeneric.h"
#include "doomstat.h"
#include "g_game.h"
#include "f_finale.h"
#include "wi_stuff.h"
#include "i_system.h"
#include "p_saveg.h"
#include <stdio.h>
#include <stdlib.h>

extern int finalestage;
extern int finalecount;
extern gameaction_t gameaction;
static int seen[5][10], total, endings;
static int expected_episode = 1, expected_map = 1;
static int last_episode, last_map, last_state = -1, last_art = -1;
static int scene_frame, scene_tic;
static int exited;
static int save_phase, saved_health;

static void require(int ok, const char *message) {
    if (!ok) { fprintf(stderr, "PROGRESSION FAIL: %s\n", message); exit(1); }
}
static unsigned int framebuffer_hash(void) {
    unsigned int h = 2166136261u;
    for (int i = 0; i < DOOMGENERIC_RESX * DOOMGENERIC_RESY; i++)
        h = (h ^ DG_ScreenBuffer[i]) * 16777619u;
    return h;
}
void TerminalTest_Tick(int frames) {
    int art = gamestate == GS_FINALE ? finalestage : -1;
    if (gameepisode != last_episode || gamemap != last_map || (int)gamestate != last_state || art != last_art) {
        last_episode = gameepisode; last_map = gamemap;
        last_state = gamestate; last_art = art;
        scene_frame = frames; scene_tic = gametic;
    }
    if (frames - scene_frame < 2 || gametic - scene_tic < 2) return;
    if (gamestate == GS_LEVEL && !exited) {
        require(gameepisode == expected_episode && gamemap == expected_map, "unexpected next map");
        require(players[consoleplayer].mo != NULL, "player not spawned");
        if (!save_phase) {
            saved_health = players[consoleplayer].health;
            G_SaveGame(5, "progress-test");
            save_phase = 1;
            return;
        }
        if (save_phase == 1) {
            unsigned char header[43];
            FILE *file = fopen(P_SaveGameFile(5), "rb");
            if (!file) return;
            size_t size = fread(header, 1, sizeof(header), file);
            fclose(file);
            if (size != sizeof(header) || header[41] != gameepisode || header[42] != gamemap) return;
            G_LoadGame(P_SaveGameFile(5));
            save_phase = 2;
            return;
        }
        if (gameaction != ga_nothing) return;
        require(players[consoleplayer].health == saved_health, "save/load changed health");
        require(!seen[gameepisode][gamemap]++, "map visited twice");
        total++;
        fprintf(stderr, "PROGRESSION MAP E%dM%d rendered saved loaded hash=%08x\n", gameepisode, gamemap, framebuffer_hash());
        const int secret_from[] = {0, 3, 5, 6, 2};
        const int return_to[] = {0, 4, 6, 7, 3};
        if (gamemap == secret_from[gameepisode]) {
            expected_map = 9;
            G_SecretExitLevel();
        } else {
            expected_map = gamemap == 9 ? return_to[gameepisode] : gamemap + 1;
            G_ExitLevel();
        }
        exited = 1;
    } else if (gamestate == GS_INTERMISSION) {
        // Accelerate the actual WI state machine, including its input checks.
        for (int i = 0; i < 5000 && gameaction != ga_worlddone; i++) {
            players[consoleplayer].cmd.buttons = i % 2 ? BT_ATTACK : 0;
            WI_Ticker();
        }
        players[consoleplayer].cmd.buttons = 0;
        require(gameaction == ga_worlddone, "intermission failed to advance");
        exited = 0;
        save_phase = 0;
    } else if (gamestate == GS_FINALE && finalestage == 0) {
        require(gamemap == 8, "finale on non-final map");
        fprintf(stderr, "PROGRESSION TEXT E%d rendered hash=%08x\n", gameepisode, framebuffer_hash());
        for (int i = 0; i < 20000 && finalestage == 0; i++) F_Ticker();
        require(finalestage == 1, "finale artwork did not start");
        // Episode 3 has a scrolling ending; reach its final END6 overlay.
        if (gameepisode == 3) while (finalecount < 1235) F_Ticker();
    } else if (gamestate == GS_FINALE && finalestage == 1) {
        endings++;
        fprintf(stderr, "PROGRESSION END E%d rendered hash=%08x\n", gameepisode, framebuffer_hash());
        if (gameepisode == 4) {
            require(total == 36 && endings == 4, "campaign coverage incomplete");
            fprintf(stderr, "PROGRESSION PASS maps=36 endings=4\n");
            I_Quit();
            exit(0);
        }
        expected_episode = gameepisode + 1;
        expected_map = 1;
        exited = 0;
        save_phase = 0;
        G_DeferedInitNew(sk_medium, expected_episode, 1);
    }
}
