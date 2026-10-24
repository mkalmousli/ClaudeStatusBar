/* Per-instance settings: a few key=value lines in <root>/<key>/conf. */
#include "cb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void cfg_load(const char *key, ICfg *c) {
    char p[600], *t, *line, *rest;
    memset(c, 0, sizeof *c);
    snprintf(p, sizeof p, "%s/%s/conf", root(), key);
    if (!(t = readfile(p, NULL))) return;
    for (rest = t; (line = strsep(&rest, "\n")); ) {
        char *v = strchr(line, '=');
        if (!v) continue;
        *v++ = 0;
        if (!strcmp(line, "perfect")) c->perfect = atoi(v);
        else if (!strcmp(line, "cost")) c->cost = atof(v);
        else if (!strcmp(line, "optout")) c->optout = atoi(v);
        else if (!strcmp(line, "mcl_flag")) c->mcl_flag = atoi(v);
        else if (!strcmp(line, "chain")) snprintf(c->chain, sizeof c->chain, "%s", v);
        else if (!strcmp(line, "orig")) { snprintf(c->orig, sizeof c->orig, "%s", v); c->has_orig = 1; }
    }
    free(t);
}

void cfg_save(const char *key, const ICfg *c) {
    char p[600], b[2800];
    snprintf(p, sizeof p, "%s/%s", root(), key);
    mkdirs(p);
    snprintf(p, sizeof p, "%s/%s/conf", root(), key);
    int n = snprintf(b, sizeof b, "perfect=%d\ncost=%g\nmcl_flag=%d\noptout=%d\n", c->perfect, c->cost, c->mcl_flag, c->optout);
    if (*c->chain) n += snprintf(b + n, sizeof b - (size_t)n, "chain=%s\n", c->chain);
    if (c->has_orig) n += snprintf(b + n, sizeof b - (size_t)n, "orig=%s\n", c->orig);
    writefile(p, b, (size_t)n);
}

/* Global switch: <root>/global holds autoupdate=0 when updates are off. */
int autoupdate(void) {
    char p[600], *t;
    snprintf(p, sizeof p, "%s/global", root());
    t = readfile(p, NULL);
    int on = !(t && strstr(t, "autoupdate=0"));
    free(t);
    return on;
}

void autoupdate_set(int on) {
    char p[600];
    mkdirs(root());
    snprintf(p, sizeof p, "%s/global", root());
    writefile(p, on ? "autoupdate=1\n" : "autoupdate=0\n", 13);
}
