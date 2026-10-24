/* Profiles: a Claude login with its own config dir (the default, or an mcl instance).
 * Add and remove them, and run claude as one. mcl is used when installed; without it
 * a plain ~/.mcl/<name> directory is the same thing as far as claudebar is concerned. */
#include "cb.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static const char *home(void) { return getenv("HOME") ? getenv("HOME") : "."; }

static int mcl_path(char *o, size_t n) {
    char list[2048], *s;
    snprintf(list, sizeof list, "%s:%s/.local/bin", getenv("PATH") ? getenv("PATH") : "", home());
    for (s = strtok(list, ":"); s; s = strtok(NULL, ":")) {
        snprintf(o, n, "%s/mcl", s);
        if (access(o, X_OK) == 0) return 1;
    }
    return 0;
}

static int valid(const char *n) {
    if (!*n || strlen(n) > 60 || n[0] == '.') return 0;
    for (; *n; n++) if (!isalnum((unsigned char)*n) && !strchr("-_.", *n)) return 0;
    return 1;
}

/* NULL on success, else a message fit to show the user. */
const char *profile_add(const char *name, int share) {
    char m[600], c[1000], d[700];
    Inst x;
    if (!valid(name) || !strcmp(name, "default")) return "Use letters, numbers, - and _ for the name.";
    if (find_inst(name, &x)) return "A profile with that name already exists.";
    if (mcl_path(m, sizeof m)) {
        snprintf(c, sizeof c, "'%s' new '%s'%s >/dev/null 2>&1", m, name, share ? " --share" : "");
        return system(c) ? "mcl could not create the profile." : NULL;
    }
    snprintf(d, sizeof d, "%s/%s", getenv("MCL_HOME") ? getenv("MCL_HOME") : "", name);
    if (!getenv("MCL_HOME")) snprintf(d, sizeof d, "%s/.mcl/%s", home(), name);
    mkdirs(d);
    return access(d, F_OK) ? "Could not create the profile folder." : NULL;
}

const char *profile_remove(const Inst *i) {
    char m[600], c[1500];
    if (!i->mcl) return "The default profile cannot be removed.";
    if (!valid(i->label)) return "This profile has an unusual name; remove it by hand.";
    if (mcl_path(m, sizeof m)) snprintf(c, sizeof c, "'%s' rm '%s' -y >/dev/null 2>&1", m, i->label);
    else snprintf(c, sizeof c, "rm -rf -- '%s'", i->dir);
    if (system(c)) return "The profile could not be removed.";
    snprintf(c, sizeof c, "rm -rf -- '%s/%s'", root(), i->key);
    if (system(c)) return "Its history could not be cleared.";
    return NULL;
}

int cmd_add(int argc, char **argv) {
    const char *e = argc < 1 ? "usage: claudebar add NAME [--share]" : profile_add(argv[0], argc > 1);
    if (e) fprintf(stderr, "claudebar: %s\n", e);
    else printf("added %s; sign in with: claudebar run %s\n", argv[0], argv[0]);
    return e != NULL;
}

int cmd_remove(int argc, char **argv) {
    Inst i;
    const char *e = argc < 1 || !find_inst(argv[0], &i) ? "usage: claudebar remove NAME" : profile_remove(&i);
    if (e) fprintf(stderr, "claudebar: %s\n", e);
    return e != NULL;
}

/* claudebar run NAME [claude args]: claude, signed in as that profile. */
int cmd_run(int argc, char **argv) {
    Inst i;
    char m[600], *a[64];
    int n = 0;
    if (argc < 1 || argc > 60 || !find_inst(argv[0], &i)) { fprintf(stderr, "claudebar: no such profile\n"); return 1; }
    if (i.mcl && mcl_path(m, sizeof m)) {
        a[n++] = m, a[n++] = argv[0];
        for (int k = 1; k < argc; k++) a[n++] = argv[k];
        a[n] = NULL;
        execv(m, a);
    }
    if (i.mcl) setenv("CLAUDE_CONFIG_DIR", i.dir, 1);
    a[n++] = "claude";
    for (int k = 1; k < argc; k++) a[n++] = argv[k];
    a[n] = NULL;
    execvp("claude", a);
    fprintf(stderr, "claudebar: cannot run claude (is it installed?)\n");
    return 1;
}
