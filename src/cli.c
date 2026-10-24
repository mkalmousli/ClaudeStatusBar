/* Scriptable output: `status` for humans, `status --line` for panels and tmux. */
#include "cb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *PACE[] = {"on pace", "falling behind", "wasting allowance", "heavily wasting"};

static void pr(const char *n, int ok, double u, long r, long now) {
    char d[24];
    if (!ok) { printf("  %s  --\n", n); return; }
    dur(r - now, d, sizeof d);
    printf("  %s  %3.0f%%%s%s\n", n, u, r ? "  resets in " : "", r ? d : "");
}

static void one(const char *n, int ok, double u, long r, long now) {
    char d[24];
    dur(r - now, d, sizeof d);
    if (!ok) printf(" %s --", n);
    else printf(" %s %.0f%%%s%s", n, u, r ? " ↻" : "", r ? d : "");
}

static void line(const Row *r, long now) {
    printf("%s", r->i.label);
    one("5h", r->v.h5ok, r->v.h5, r->v.h5r, now);
    one("wk", r->v.wkok, r->v.wk, r->v.wkr, now);
}

int cmd_status(int argc, char **argv) {
    const char *only = NULL;
    int one = 0, shown = 0;
    long now = now_s();
    Inst all[64];
    int n = discover(all, 64);
    for (int k = 0; k < argc; k++) {
        if (!strcmp(argv[k], "--line")) one = 1;
        else if (!strcmp(argv[k], "-i") && k + 1 < argc) only = argv[++k];
    }
    for (int k = 0; k < n; k++) {
        Row *r = &rows[0];
        if (only && strcmp(only, all[k].key) && strcmp(only, all[k].label)) continue;
        memset(r, 0, sizeof *r);
        r->i = all[k];
        cfg_load(r->i.key, &r->c);
        load(r->i.key, &r->d, now);
        build_view(&r->d, now, r->c.cost, &r->v);
        if (one) { printf("%s", shown ? " | " : ""); line(r, now); }
        else {
            account(&r->i, r->acct, sizeof r->acct);
            printf("%s%s %s\n", r->i.label, r->i.mcl ? " (mcl)" : "", r->acct);
            pr("5h", r->v.h5ok, r->v.h5, r->v.h5r, now);
            if (r->v.h5ok && r->v.gap >= 0) printf("      %s\n", PACE[r->v.pace]);
            pr("wk", r->v.wkok, r->v.wk, r->v.wkr, now);
            if (r->v.left >= 0) printf("      ~%.0f%%/session, %.1f sessions left, %.0f%% waste\n", r->v.burn, r->v.left, r->v.waste);
        }
        data_free(&r->d);
        shown++;
    }
    if (one) puts("");
    return shown ? 0 : 1;
}

/* claudebar set perfect on|off | cost N   [-i name] */
int cmd_set(int argc, char **argv) {
    Inst all[64];
    const char *only = NULL;
    int n = discover(all, 64), done = 0;
    for (int k = 2; k < argc; k++) if (!strcmp(argv[k], "-i") && k + 1 < argc) only = argv[++k];
    if (argc >= 2 && !strcmp(argv[0], "autoupdate")) { autoupdate_set(!strcmp(argv[1], "on")); return 0; }
    if (argc < 3) return 2;
    for (int k = 0; k < n; k++) {
        ICfg c;
        if (only && strcmp(only, all[k].key) && strcmp(only, all[k].label)) continue;
        cfg_load(all[k].key, &c);
        if (!strcmp(argv[0], "perfect")) c.perfect = !strcmp(argv[1], "on");
        else if (!strcmp(argv[0], "cost")) c.cost = atof(argv[1]);
        else return 2;
        cfg_save(all[k].key, &c);
        done++;
    }
    return done ? 0 : 1;
}
