/* The user-system side: where the binary lives, and installing it for good. */
#include "cb.h"
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

int quiet;

static const char *home(void) { return getenv("HOME") ? getenv("HOME") : "."; }

static const char *stable(void) {
    static char p[600];
    snprintf(p, sizeof p, "%s/.local/bin/claudebar", home());
    return p;
}

static const char *self(void) {
    static char p[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", p, sizeof p - 1);
    if (n <= 0) return stable();
    p[n] = 0;
    if (n > 4 && !strcmp(p + n - 4, "-gui")) p[n - 4] = 0; /* the GUI hooks the CLI, not itself */
    return p;
}

/* The installed copy when there is one, else whatever is running. */
const char *bin_path(void) { return access(stable(), X_OK) == 0 ? stable() : self(); }

/* Hook every instance that is not hooked yet, unless the user uninstalled it. */
void auto_capture(void) {
    Inst all[64];
    int n = discover(all, 64);
    quiet = 1;
    for (int k = 0; k < n; k++) {
        ICfg c;
        cfg_load(all[k].key, &c);
        if (!c.optout) cmd_install(&all[k], 1);
    }
    quiet = 0;
}

static void put(const char *from, const char *to) {
    char dir[600], *b, *sl;
    size_t n;
    if (!strcmp(from, to) || !(b = readfile(from, &n))) return;
    snprintf(dir, sizeof dir, "%s", to);
    sl = strrchr(dir, '/');
    *sl = 0;
    mkdirs(dir);
    if (writefile(to, b, n) == 0) chmod(to, 0755);
    free(b);
}

/* The binary, and the GUI next to it when there is one. */
static void copy_self(void) {
    char g[600], d[600];
    put(self(), stable());
    sibling(g, sizeof g, self(), "claudebar-gui");
    sibling(d, sizeof d, stable(), "claudebar-gui");
    put(g, d);
    printf("binary: %s\n", stable());
}

int cmd_system(int on) {
    Inst all[64];
    if (on) copy_self();
    int n = discover(all, 64), ok = 1;
    for (int k = 0; k < n; k++) cmd_install(&all[k], on);
    if (desktop(on)) printf("gui: %s\n", on ? "menu entry + autostart (tray icon)" : "removed");
    if (!service(on)) printf("service: not set up (no systemd/launchd); run `claudebar daemon` yourself\n");
    else printf("service: %s\n", on ? "running (Perfect Use, auto capture, auto update)" : "removed");
    if (on && !strstr(getenv("PATH") ? getenv("PATH") : "", ".local/bin"))
        printf("note: add %s/.local/bin to your PATH\n", home());
    if (!on) { unlink(stable()); printf("removed binary; data kept in %s\n", root()); }
    return !ok;
}
