/* How much of the weekly limit one 5h session costs. */
#include "cb.h"
#include <string.h>

typedef struct { long hr; double peak; } Win;

/* Windows already closed this week, oldest first, with the weekly peak in each. */
static int closed(const Data *d, long wkr, long now, Win *w, int max) {
    int n = 0;
    for (int i = 0; i < d->np; i++) {
        const Point *p = &d->p[i];
        if (p->wr != wkr || p->hr <= 0 || p->hr > now || p->w < 0) continue;
        int k = 0;
        while (k < n && w[k].hr != p->hr) k++;
        if (k == n) {
            if (n == max) continue;
            w[n++] = (Win){p->hr, p->w};
        } else if (p->w > w[k].peak) w[k].peak = p->w;
    }
    for (int i = 1; i < n; i++)  /* insertion sort by window end */
        for (int j = i; j > 0 && w[j].hr < w[j - 1].hr; j--) { Win t = w[j]; w[j] = w[j - 1]; w[j - 1] = t; }
    return n;
}

/* src: 1 = measured from closed windows, 2 = estimated from the slope, 0 = unknown */
double burn_rate(const Data *d, long wkr, double wk, long now, int *src) {
    Win w[64];
    int n = closed(d, wkr, now, w, 64);
    *src = 0;
    if (n >= 2) { *src = 1; return (w[n - 1].peak - w[0].peak) / (n - 1); }
    if (n == 1 && w[0].peak > 0) { *src = 1; return w[0].peak; }
    long t0 = 0, t1 = 0; double v0 = 0, v1 = 0;
    for (int i = 0; i < d->np; i++) {
        const Point *p = &d->p[i];
        if (p->wr != wkr || p->w < 0 || p->t < now - H5) continue;
        if (!t0) { t0 = p->t; v0 = p->w; }
        t1 = p->t; v1 = p->w;
    }
    if (t1 - t0 < 900 || v1 <= v0) return 0;
    *src = 2;
    (void)wk;
    return (v1 - v0) * (double)H5 / (double)(t1 - t0);
}
