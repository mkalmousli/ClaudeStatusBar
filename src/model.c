/* From raw snapshots to "how am I doing": windows, pace, projection, waste. */
#include "cb.h"
#include <string.h>

/* Gap = elapsed % of the 5h window minus used %: how far usage trails the clock. */
static const double PACE[] = {15, 35, 60};
#define CRITICAL 60.0

/* The open window: newest reset still ahead, then the highest reading in it. */
static int pick(const Data *d, long now, int wk, double *used, long *reset) {
    long best = -1;
    int found = 0;
    for (int i = 0; i < d->ns; i++) {
        double u = wk ? d->s[i].wk : d->s[i].h5;
        long r = wk ? d->s[i].wkr : d->s[i].h5r;
        if (u < 0 || (r && r <= now)) continue;
        if (r > best) { best = r; found = 0; }
        if (r == best && (!found || u > *used)) { *used = u; found = 1; }
    }
    *reset = best > 0 ? best : 0;
    return best >= 0;
}

static void pace(View *v, long now) {
    long rem = v->h5r - now;
    double elapsed = (double)(H5 - rem) * 100.0 / H5;
    if (elapsed < 0) elapsed = 0;
    if (elapsed > 100) elapsed = 100;
    v->gap = elapsed - v->h5;
    v->pace = v->gap < PACE[0] ? 0 : v->gap < PACE[1] ? 1 : v->gap < PACE[2] ? 2 : 3;
    if (v->gap < CRITICAL) {  /* if usage stays flat, when does it turn critical? */
        v->crit_in = (long)((CRITICAL - v->gap) * H5 / 100.0);
        if (v->crit_in > rem) v->crit_in = rem;
    }
}

/* Sessions left this week: bounded by allowance and by the weekly clock. */
static void project(View *v, long now) {
    if (v->burn <= 0) return;
    v->wend = v->wk + v->burn > 100 ? 100 : v->wk + v->burn;
    v->left = (100 - v->wk) / v->burn;
    if (v->h5r && v->wkr) {
        double by_clock = (double)((v->wkr - v->h5r > 0 ? v->wkr - v->h5r : 0) / H5);
        if (by_clock < v->left) {
            v->left = by_clock;
            v->clock_limited = 1;
            double usable = v->wend + v->left * v->burn;
            v->waste = usable >= 100 ? 0 : 100 - usable;
        }
    }
    (void)now;
}

void build_view(const Data *d, long now, double cost_override, View *v) {
    memset(v, 0, sizeof *v);
    v->gap = v->left = v->wend = -1;
    v->h5ok = pick(d, now, 0, &v->h5, &v->h5r);
    v->wkok = pick(d, now, 1, &v->wk, &v->wkr);
    for (int i = 0; i < d->ns; i++) if (d->s[i].ts > v->newest) v->newest = d->s[i].ts;
    if (v->h5ok && v->h5r) pace(v, now);
    if (!v->wkok) return;
    if (cost_override > 0) { v->burn = cost_override > 100 ? 100 : cost_override; v->src = 3; }
    else v->burn = burn_rate(d, v->wkr, v->wk, now, &v->src);
    project(v, now);
}
