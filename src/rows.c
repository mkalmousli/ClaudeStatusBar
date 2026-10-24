/* The rows both front ends show: one per Claude instance, re-read from disk. */
#include "cb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

Row rows[64];
int nrows, sel;

void rows_reload(void) {
    Inst all[64];
    char keep[80];
    long now = now_s();
    snprintf(keep, sizeof keep, "%s", nrows ? rows[sel].i.key : "");
    for (int k = 0; k < nrows; k++) data_free(&rows[k].d);
    nrows = discover(all, 64);
    for (int k = 0; k < nrows; k++) {
        Row *r = &rows[k];
        char p[600], *t;
        r->i = all[k];
        cfg_load(r->i.key, &r->c);
        load(r->i.key, &r->d, now);
        build_view(&r->d, now, r->c.cost, &r->v);
        account(&r->i, r->acct, sizeof r->acct);
        snprintf(p, sizeof p, "%s/settings.json", r->i.dir);
        t = readfile(p, NULL);
        r->installed = t && strstr(t, "claudebar") != NULL;
        free(t);
        if (!strcmp(r->i.key, keep)) sel = k;
    }
    if (sel >= nrows) sel = nrows ? nrows - 1 : 0;
}
