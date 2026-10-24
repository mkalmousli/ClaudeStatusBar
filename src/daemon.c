#include "cb.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#define DAY 86400L

/* Checked at most once a day, remembered across restarts. */
static int update_due(void) {
    char p[600], *t;
    snprintf(p, sizeof p, "%s/lastcheck", root());
    t = readfile(p, NULL);
    long last = t ? atol(t) : 0, now = now_s();
    free(t);
    if (!autoupdate() || now - last < DAY) return 0;
    char b[32];
    int n = snprintf(b, sizeof b, "%ld\n", now);
    writefile(p, b, (size_t)n);
    return 1;
}

/* Headless: hooks new instances, runs Perfect Use, keeps the binary current. */
int cmd_daemon(void) {
    Inst all[64];
    for (;;) {
        auto_capture();
        int n = discover(all, 64);
        for (int i = 0; i < n; i++) perfect_tick(&all[i]);
        if (update_due() && do_update(1) == 2) execl(bin_path(), "claudebar", "daemon", (char *)NULL);
        sleep(30);
    }
}
