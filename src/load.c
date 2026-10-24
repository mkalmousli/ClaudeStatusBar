/* Reading the per-session files and the history back. */
#include "cb.h"
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int snap_parse(char *line, Snap *s) {
    char *f[11] = {0}, *p = line;
    int n = 0;
    while (n < 11 && p) f[n++] = strsep(&p, "\t");
    if (n < 11) return 0;
    s->ts = atol(f[0]); snprintf(s->sid, sizeof s->sid, "%s", f[1]);
    s->h5 = atof(f[2]); s->wk = atof(f[3]); s->h5r = atol(f[4]); s->wkr = atol(f[5]);
    s->cost = atof(f[6]); s->ctx = atof(f[7]); s->ht = atol(f[8]);
    snprintf(s->model, sizeof s->model, "%s", f[9]);
    snprintf(s->cwd, sizeof s->cwd, "%s", f[10]);
    s->cwd[strcspn(s->cwd, "\n")] = 0;
    return 1;
}

static int by_ts(const void *a, const void *b) {
    long x = ((const Snap *)a)->ts, y = ((const Snap *)b)->ts;
    return (x < y) - (x > y);
}

void data_free(Data *d) { free(d->s); free(d->p); memset(d, 0, sizeof *d); }

void load(const char *key, Data *d, long now) {
    char dir[600], f[900];
    memset(d, 0, sizeof *d);
    snprintf(dir, sizeof dir, "%s/%s", root(), key);
    DIR *dp = opendir(dir);
    struct dirent *e;
    while (dp && (e = readdir(dp))) {
        size_t l = strlen(e->d_name);
        if (l < 6 || strcmp(e->d_name + l - 5, ".snap")) continue;
        snprintf(f, sizeof f, "%s/%s", dir, e->d_name);
        char *t = readfile(f, NULL);
        Snap s = {0};
        if (t && snap_parse(t, &s)) {
            if (now - s.ts > 86400) unlink(f);
            else if ((d->s = realloc(d->s, sizeof(Snap) * (size_t)(d->ns + 1)))) d->s[d->ns++] = s;
        }
        free(t);
    }
    if (dp) closedir(dp);
    if (d->ns) qsort(d->s, (size_t)d->ns, sizeof(Snap), by_ts);
    snprintf(f, sizeof f, "%s/%s/history.txt", root(), key);
    FILE *fh = fopen(f, "r");
    Point p;
    while (fh && fscanf(fh, "%ld %lf %lf %ld %ld", &p.t, &p.h, &p.w, &p.hr, &p.wr) == 5)
        if (now - p.t < 14 * 86400 && (d->p = realloc(d->p, sizeof(Point) * (size_t)(d->np + 1))))
            d->p[d->np++] = p;
    if (fh) fclose(fh);
}
