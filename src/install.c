/* Wire capture into one instance's settings.json, and undo it exactly. */
#include "cb.h"
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void path_of(char *o, size_t n, const Inst *i, const char *f) { snprintf(o, n, "%s/%s", i->dir, f); }

#define say(...) do { if (!quiet) printf(__VA_ARGS__); } while (0)

/* mcl injects its own status line per launch; this is the command it uses. */
static int mcl_chain(char *o, size_t n) {
    char real[PATH_MAX], line[512];
    FILE *p = popen("command -v mcl", "r");
    if (!p) return 0;
    int ok = fgets(line, sizeof line, p) != NULL;
    pclose(p);
    line[strcspn(line, "\n")] = 0;
    if (!ok || !realpath(line, real)) return 0;
    FILE *f = fopen(real, "r");
    if (!f) return 0;
    ok = fgets(line, sizeof line, f) != NULL && !strncmp(line, "#!", 2);
    fclose(f);
    line[strcspn(line, "\n")] = 0;
    if (ok) snprintf(o, n, "%s -m mcl.statusline", line + 2);
    return ok;
}

static void patch(const char *file, char *(*op)(const char *, const char *), const char *key) {
    char *t = readfile(file, NULL), *out;
    if (!t) t = strdup("{}");
    if ((out = op(t, key))) { writefile(file, out, strlen(out)); free(out); }
    free(t);
}

static char *mcl_off(const char *j, const char *k) { return jset(j, k, "false"); }

static int install(const Inst *i, ICfg *c, const char *sp, char *js) {
    char cmd[1024] = "", raw[1024], neu[4400], bak[640];
    const char *cur = jlocate(js, "statusLine", NULL);
    if (cur) jstr(jpath(cur, "command"), cmd, sizeof cmd);
    if (strstr(cmd, "claudebar")) { say("%s: already installed\n", i->label); return 0; }
    c->has_orig = cur != NULL;
    if (cur) {
        snprintf(raw, sizeof raw, "%.*s", (int)(jskip(cur) - cur), cur);
        for (char *p = raw; *p; p++) if (*p == '\n' || *p == '\r') *p = ' ';
        memcpy(c->orig, raw, sizeof c->orig);
    }
    if (!*cmd && i->mcl) mcl_chain(cmd, sizeof cmd);
    memcpy(c->chain, cmd, sizeof c->chain);
    if (i->mcl) { path_of(raw, sizeof raw, i, ".mcl.json"); patch(raw, mcl_off, "statusline"); c->mcl_flag = 1; }
    snprintf(bak, sizeof bak, "%s.claudebar-bak", sp);
    if (access(bak, F_OK)) writefile(bak, js, strlen(js));
    snprintf(neu, sizeof neu, "{\"type\":\"command\",\"command\":\"%s statusline -i %s\",\"refreshInterval\":5}", bin_path(), i->key);
    char *out = jset(js, "statusLine", neu);
    if (!out) { fprintf(stderr, "%s: settings.json is not a JSON object\n", i->label); return 1; }
    writefile(sp, out, strlen(out));
    free(out);
    c->optout = 0;
    cfg_save(i->key, c);
    say("%s: installed%s\n", i->label, *c->chain ? " (chaining your existing status line)" : "");
    return 0;
}

int cmd_install(const Inst *i, int on) {
    char sp[600], mp[600], *js, *out;
    ICfg c;
    cfg_load(i->key, &c);
    path_of(sp, sizeof sp, i, "settings.json");
    js = readfile(sp, NULL);
    if (on) { int r = install(i, &c, sp, js ? js : strdup("{}")); free(js); return r; }
    if (!js || (!*c.chain && !c.has_orig && !c.mcl_flag)) { say("%s: not installed\n", i->label); c.optout = 1; cfg_save(i->key, &c); free(js); return 0; }
    out = c.has_orig ? jset(js, "statusLine", c.orig) : jdel(js, "statusLine");
    if (out) { writefile(sp, out, strlen(out)); free(out); }
    if (c.mcl_flag) { path_of(mp, sizeof mp, i, ".mcl.json"); patch(mp, jdel, "statusline"); }
    c.chain[0] = c.orig[0] = 0; c.has_orig = c.mcl_flag = 0; c.optout = 1; /* stay off: no auto capture */
    cfg_save(i->key, &c);
    free(js);
    say("%s: restored\n", i->label);
    return 0;
}
