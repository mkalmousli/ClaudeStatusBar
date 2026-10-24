/* The interactive view: state, timers and keys. Drawing lives in draw.c. */
#include "cb.h"
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int detail;
char msg[160];

static void bye(int s) { (void)s; term_raw(0); _exit(0); }

static void act(int k) {
    Row *r = &rows[sel];
    if (!nrows) return;
    if (k == 'p') { r->c.perfect = !r->c.perfect; cfg_save(r->i.key, &r->c); }
    else if (k == '+') { r->c.cost += 1; cfg_save(r->i.key, &r->c); }
    else if (k == '-') { r->c.cost = r->c.cost >= 1 ? r->c.cost - 1 : 0; cfg_save(r->i.key, &r->c); }
    else if (k == 'i') { cmd_install(&r->i, !r->installed); printf("\x1b[?1049h"); }
    else if (k == 's') {
        perfect_start(&r->i);
        snprintf(msg, sizeof msg, "started a 5h session on %s", r->i.label);
    }
}

int cmd_tui(void) {
    long t_reload = 0, t_tick = 0;
    if (!isatty(0) || !isatty(1)) return cmd_status(0, NULL);
    signal(SIGINT, bye);
    signal(SIGTERM, bye);
    term_raw(1);
    for (;;) {
        long now = now_s();
        if (now - t_reload >= 1) { rows_reload(); t_reload = now; }
        if (now - t_tick >= 30) {
            auto_capture();
            for (int k = 0; k < nrows; k++) perfect_tick(&rows[k].i);
            t_tick = now;
        }
        draw();
        int k = term_key(250);
        if (k == 'q' || (k == 27 && !detail)) break;
        if (k == 27 || k == 1000 + 'D') detail = 0;
        else if (k == 'j' || k == 1000 + 'B') sel = sel + 1 < nrows ? sel + 1 : sel;
        else if (k == 'k' || k == 1000 + 'A') sel = sel > 0 ? sel - 1 : 0;
        else if (k == '\n' || k == 1000 + 'C') detail = !detail || k == '\n' ? !detail : 1;
        else if (k > 0) { act(k); if (k != 's') msg[0] = 0; t_reload = 0; }
    }
    term_raw(0);
    return 0;
}
