/* Open a terminal running `claudebar run NAME`, whichever desktop this is. */
#include "g_gui.h"

/* Terminal emulators and the flag each wants before the command. */
static const char *T[][2] = {{"xdg-terminal-exec", ""}, {"x-terminal-emulator", "-e"}, {"gnome-terminal", "--"},
    {"kgx", "-e"}, {"konsole", "-e"}, {"xfce4-terminal", "-x"}, {"mate-terminal", "-x"}, {"lxterminal", "-e"},
    {"alacritty", "-e"}, {"kitty", ""}, {"foot", ""}, {"wezterm", "start"}, {"xterm", "-e"}};

int term_run(const char *profile) {
    char cli[700];
    sibling(cli, sizeof cli, bin_path(), "claudebar");
    for (guint k = 0; k <= G_N_ELEMENTS(T); k++) {
        const char *t = k ? T[k - 1][0] : g_getenv("TERMINAL"), *flag = k ? T[k - 1][1] : "-e";
        char *p = t ? g_find_program_in_path(t) : NULL, *argv[7];
        int n = 0;
        if (!p) continue;
        argv[n++] = p;
        if (*flag) argv[n++] = (char *)flag;
        argv[n++] = cli, argv[n++] = "run", argv[n++] = (char *)profile, argv[n] = NULL;
        gboolean ok = g_spawn_async(NULL, argv, NULL, G_SPAWN_DEFAULT, NULL, NULL, NULL, NULL);
        g_free(p);
        if (ok) return 1;
    }
    return 0;
}
