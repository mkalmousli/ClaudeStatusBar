/* One small file per session (no locks); append-only history per instance. */
#include "cb.h"
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void path(char *o, size_t n, const char *key, const char *file) {
    snprintf(o, n, "%s/%s/%s", root(), key, file);
}

static long epoch(const char *v) {
    double x = jnum(v, 0);
    return x > 1e12 ? (long)(x / 1000) : (long)x;
}

/* Used % of a rate-limit bucket; -1 when absent. */
static double used(const char *j, const char *b, long *reset) {
    char p[64];
    snprintf(p, sizeof p, "rate_limits.%s.resets_at", b);
    *reset = epoch(jpath(j, p));
    snprintf(p, sizeof p, "rate_limits.%s.used_percentage", b);
    return jnum(jpath(j, p), -1);
}

static void clean(char *s) { for (; *s; s++) if (*s == '\t' || *s == '\n') *s = ' '; }

void record(const char *key, const char *json) {
    Snap s = {0}, o = {0};
    char sid[65] = "default", f[700], dir[600], buf[1024], eff[24] = "", mdl[40] = "";
    jstr(jpath(json, "session_id"), sid, sizeof sid);
    for (char *c = sid; *c; c++) if (*c == '/' || *c == '.') *c = '_';
    s.ts = now_s(); snprintf(s.sid, sizeof s.sid, "%s", sid);
    s.h5 = used(json, "five_hour", &s.h5r); s.wk = used(json, "seven_day", &s.wkr);
    jstr(jpath(json, "model.display_name"), mdl, sizeof mdl);
    jstr(jpath(json, "effort.level"), eff, sizeof eff);
    snprintf(s.model, sizeof s.model, "%s%s%s", mdl, *eff ? "·" : "", eff);
    jstr(jpath(json, "workspace.current_dir"), s.cwd, sizeof s.cwd);
    s.cost = jnum(jpath(json, "cost.total_cost_usd"), 0);
    s.ctx = jnum(jpath(json, "context_window.used_percentage"), 0);
    snprintf(dir, sizeof dir, "%s/%s", root(), key); mkdirs(dir);
    snprintf(f, sizeof f, "%s/%s.snap", dir, sid);
    char *old = readfile(f, NULL);
    int had = old && snap_parse(old, &o);
    if (had) { /* Claude drops optional blocks on mode changes: keep what we knew */
        if (s.h5 < 0) { s.h5 = o.h5; s.h5r = o.h5r; }
        if (s.wk < 0) { s.wk = o.wk; s.wkr = o.wkr; }
        if (!*s.model) memcpy(s.model, o.model, sizeof s.model);
        if (!*s.cwd) memcpy(s.cwd, o.cwd, sizeof s.cwd);
        if (s.cost == 0) s.cost = o.cost;
        s.ht = o.ht;
    }
    free(old);
    if ((s.h5 >= 0 || s.wk >= 0) && (!had || o.h5 != s.h5 || o.wk != s.wk || s.ts - o.ht >= 300)) {
        s.ht = s.ts;
        char h[640];
        path(h, sizeof h, key, "history.txt");
        FILE *fh = fopen(h, "a");
        if (fh) { fprintf(fh, "%ld %g %g %ld %ld\n", s.ts, s.h5, s.wk, s.h5r, s.wkr); fclose(fh); }
    }
    clean(s.model); clean(s.cwd);
    int n = snprintf(buf, sizeof buf, "%ld\t%s\t%g\t%g\t%ld\t%ld\t%g\t%g\t%ld\t%s\t%s\n", s.ts, s.sid,
                     s.h5, s.wk, s.h5r, s.wkr, s.cost, s.ctx, s.ht, s.model, s.cwd);
    writefile(f, buf, (size_t)n);
}
