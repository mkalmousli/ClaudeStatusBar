/* The hot path: Claude Code runs this on every refresh, so it does the least
 * possible: record one small file, hand the payload on, print. */
#include "cb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void compact(const char *j) {
    char t[2][32], c[2][32];
    const char *b[] = {"five_hour", "seven_day"}, *n[] = {"5h", "wk"};
    char p[64];
    for (int k = 0; k < 2; k++) {
        snprintf(p, sizeof p, "rate_limits.%s.used_percentage", b[k]);
        double u = jnum(jpath(j, p), -1);
        snprintf(p, sizeof p, "rate_limits.%s.resets_at", b[k]);
        long r = (long)jnum(jpath(j, p), 0);
        if (u < 0) snprintf(t[k], sizeof t[k], "%s --", n[k]);
        else snprintf(t[k], sizeof t[k], "%s %.0f%%", n[k], u);
        if (r) { dur(r - now_s(), c[k], sizeof c[k]); strcat(t[k], " ↻"); strcat(t[k], c[k]); }
    }
    printf("%s  %s\n", t[0], t[1]);
}

int cmd_statusline(const char *key) {
    size_t n = 0;
    char *raw = readall(0, &n);
    ICfg c;
    if (!raw || !n) return 0;
    cfg_load(key, &c);
    record(key, raw);
    if (*c.chain) {
        FILE *ch = popen(c.chain, "w");
        if (ch) { fwrite(raw, 1, n, ch); pclose(ch); }
    } else compact(raw);
    free(raw);
    return 0;
}
