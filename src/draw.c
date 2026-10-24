#include "cb.h"
#include <stdio.h>
#include <string.h>

static const int RGB[][3] = {{12, 163, 12}, {250, 178, 25}, {236, 131, 90}, {242, 85, 90}};
const char *pace_name[] = {"on pace", "falling behind", "wasting allowance", "heavily wasting"};
#define BW 28

static void colour(double pct) { int c = pct < 50 ? 0 : pct < 75 ? 1 : pct < 90 ? 2 : 3;
    printf("\x1b[38;2;%d;%d;%dm", RGB[c][0], RGB[c][1], RGB[c][2]); }

/* A meter with a ┃ marking how much of the window's time is gone. */
static void bar(double used, double elapsed) {
    int fill = (int)(used / 100 * BW + 0.5), mark = elapsed < 0 ? -1 : (int)(elapsed * BW);
    for (int k = 0; k < BW; k++) {
        if (k == mark) printf("\x1b[0;1m┃");
        else if (k < fill) { colour(used); fputs("█", stdout); }
        else fputs("\x1b[0;90m░", stdout);
    }
    fputs("\x1b[0m", stdout);
}

static void limit(const char *name, int ok, double used, long reset, long span, long now) {
    char d[24], c[24];
    printf("  %s ", name);
    if (!ok) { puts("\x1b[90m-- not started / no data\x1b[0m\x1b[K"); return; }
    bar(used, reset ? (double)(span - (reset - now)) / (double)span : -1);
    colour(used);
    printf(" %3.0f%%\x1b[0m", used);
    if (reset) { dur(reset - now, d, sizeof d); clock_str(reset, c, sizeof c); printf("  ↻ %s (%s)", d, c); }
}

static void card(const Row *r, int selected, long now) {
    const View *v = &r->v;
    char age[24], b[48] = "";
    dur(now - v->newest, age, sizeof age);
    printf("%s\x1b[1m%s\x1b[0m \x1b[90m%s%s%s\x1b[0m\x1b[K\n", selected ? "▶ " : "  ", r->i.label,
           r->acct, r->installed ? "" : "  · capture OFF (press i)",
           r->c.perfect ? "  · perfect use ON" : "");
    limit("5h", v->h5ok, v->h5, v->h5r, H5, now);
    if (v->h5ok && v->gap >= 0) { colour(v->gap * 1.5); printf("  %s", pace_name[v->pace]); }
    puts("\x1b[0m\x1b[K");
    limit("wk", v->wkok, v->wk, v->wkr, WK, now);
    if (v->burn > 0) snprintf(b, sizeof b, v->src == 1 ? "measured" : v->src == 3 ? "set" : "estimated");
    if (v->burn > 0 && v->left >= 0)
        printf("  \x1b[90m~%.0f%%/session (%s) · %.1f left\x1b[0m", v->burn, b, v->left);
    if (v->waste > 0) printf(" \x1b[31mwaste %.0f%%\x1b[0m", v->waste);
    printf("\x1b[K\n  \x1b[90m%d session%s%s%s%s\x1b[0m\x1b[K\n", r->d.ns, r->d.ns == 1 ? "" : "s",
           v->newest ? " · updated " : "", v->newest ? age : "", v->newest ? " ago" : "");
}

static void sessions(const Row *r, long now) {
    puts("  \x1b[90mSESSION   MODEL                CTX   COST    UPDATED  PROJECT\x1b[0m\x1b[K");
    for (int k = 0; k < r->d.ns && k < 10; k++) {
        const Snap *s = &r->d.s[k];
        char a[24], *base = strrchr(s->cwd, '/');
        dur(now - s->ts, a, sizeof a);
        printf("  %-8.8s  %-20.20s %3.0f%%  $%-6.2f %-8s %s\x1b[K\n", s->sid, s->model, s->ctx, s->cost, a, base ? base + 1 : s->cwd);
    }
    printf("\x1b[K\n  perfect use: %s   session cost: %s   [p] toggle  [+/-] cost  [s] start now  [i] capture\x1b[K\n",
           r->c.perfect ? "on" : "off", r->c.cost > 0 ? "set" : "auto");
    if (r->c.cost > 0) printf("  weekly %% per session set to %.0f\x1b[K\n", r->c.cost);
}

void draw(void) {
    static char buf[1 << 16];
    long now = now_s();
    setvbuf(stdout, buf, _IOFBF, sizeof buf);
    fputs("\x1b[H", stdout);
    printf("\x1b[1mclaudebar\x1b[0m \x1b[90m%s · %d instance%s\x1b[0m\x1b[K\n\n", VERSION, nrows, nrows == 1 ? "" : "s");
    if (!nrows) puts("  no Claude config directories found\x1b[K");
    for (int k = 0; k < nrows; k++) {
        card(&rows[k], k == sel, now);
        if (detail && k == sel) sessions(&rows[k], now);
        puts("\x1b[K");
    }
    printf("\x1b[90m%s\x1b[0m\x1b[K\n\x1b[J", *msg ? msg : "j/k select · enter details · p perfect use · i capture · r reload · q quit");
    fflush(stdout);
}
