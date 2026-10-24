/* Instances: the default ~/.claude plus every mcl instance directory. */
#include "cb.h"
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

static const char *home(void) { return getenv("HOME") ? getenv("HOME") : "."; }

static int cmp(const void *a, const void *b) { return strcmp(((const Inst *)a)->key, ((const Inst *)b)->key); }

int discover(Inst *out, int max) {
    int n = 0;
    struct stat st;
    char mroot[300];
    const char *m = getenv("MCL_HOME");
    snprintf(out[0].dir, sizeof out[0].dir, "%s/.claude", home());
    if (stat(out[0].dir, &st) == 0 && max > 0) {
        snprintf(out[0].key, sizeof out[0].key, "default");
        snprintf(out[0].label, sizeof out[0].label, "default");
        out[n++].mcl = 0;
    }
    snprintf(mroot, sizeof mroot, "%s", m ? m : "");
    if (!m) snprintf(mroot, sizeof mroot, "%s/.mcl", home());
    DIR *dp = opendir(mroot);
    struct dirent *e;
    int first = n;
    while (dp && (e = readdir(dp)) && n < max) {
        if (e->d_name[0] == '.' || strlen(e->d_name) > 60) continue;
        Inst *i = &out[n];
        snprintf(i->dir, sizeof i->dir, "%s/%.60s", mroot, e->d_name);
        if (stat(i->dir, &st) || !S_ISDIR(st.st_mode)) continue;
        snprintf(i->key, sizeof i->key, "mcl-%.60s", e->d_name);
        snprintf(i->label, sizeof i->label, "%.60s", e->d_name);
        i->mcl = 1;
        n++;
    }
    if (dp) closedir(dp);
    qsort(out + first, (size_t)(n - first), sizeof(Inst), cmp);
    return n;
}

int find_inst(const char *name, Inst *out) {
    Inst all[64];
    int n = discover(all, 64);
    for (int i = 0; i < n; i++)
        if (!strcmp(all[i].key, name) || !strcmp(all[i].label, name)) { *out = all[i]; return 1; }
    return 0;
}

/* Signed-in account email, '' when there is none. */
void account(const Inst *i, char *out, size_t n) {
    char p[600];
    const char *fmt[] = {"%s/.claude.json", "%s/.claude/.claude.json"};
    *out = 0;
    for (int k = 0; k < 3 && !*out; k++) {
        if (k < 2) snprintf(p, sizeof p, fmt[k], i->dir);
        else if (!i->mcl) snprintf(p, sizeof p, "%s/.claude.json", home());
        else break;
        char *t = readfile(p, NULL);
        if (t) jstr(jpath(t, "oauthAccount.emailAddress"), out, n);
        free(t);
    }
}
