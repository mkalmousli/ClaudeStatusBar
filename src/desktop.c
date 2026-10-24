/* Desktop integration: finding the GUI binary, menu entry and autostart. */
#include "cb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MENU ".local/share/applications/claudebar.desktop"
#define AUTO ".config/autostart/claudebar-gui.desktop"

/* The file `name` next to the executable `exe`. */
void sibling(char *o, size_t n, const char *exe, const char *name) {
    char *s;
    snprintf(o, n, "%s", exe);
    s = strrchr(o, '/');
    if (s) snprintf(s + 1, n - (size_t)(s + 1 - o), "%s", name);
}

static void full(char *o, size_t n, const char *rel) {
    snprintf(o, n, "%s/%s", getenv("HOME") ? getenv("HOME") : ".", rel);
}

static void entry(const char *rel, const char *gui, const char *args, const char *tail) {
    char p[700], b[1200], *s;
    full(p, sizeof p, rel);
    s = strrchr(p, '/');
    *s = 0;
    mkdirs(p);
    *s = '/';
    int n = snprintf(b, sizeof b, "[Desktop Entry]\nType=Application\nName=claudebar\n"
                     "Comment=Claude Code usage meter\nExec=%s%s\nIcon=utilities-system-monitor\n"
                     "Categories=Utility;Monitor;\nTerminal=false\n%s", gui, args, tail);
    writefile(p, b, (size_t)n);
}

/* Returns 1 when there is a GUI to integrate (it is optional: it needs GTK3). */
int desktop(int on) {
    char g[700], p[700];
    full(g, sizeof g, ".local/bin/claudebar-gui");
    if (!on) {
        unlink(g);
        full(p, sizeof p, MENU), unlink(p);
        full(p, sizeof p, AUTO), unlink(p);
        return 1;
    }
    if (access(g, X_OK)) return 0;
    entry(MENU, g, "", "");
    entry(AUTO, g, " --hidden", "X-GNOME-Autostart-enabled=true\n");
    return 1;
}

int cmd_gui(void) {
    char g[700];
    sibling(g, sizeof g, bin_path(), "claudebar-gui");
    if (access(g, X_OK)) {
        fprintf(stderr, "claudebar: the GUI is not installed (it needs GTK3).\n"
                        "  prebuilt: claudebar update    from source: ./build install (with libgtk-3-dev)\n");
        return 1;
    }
    execl(g, g, (char *)NULL);
    return 1;
}
