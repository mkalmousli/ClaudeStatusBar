#include "cb.h"
#include <signal.h>
#include <stdio.h>
#include <string.h>

static int each(int argc, char **argv, int on) {
    Inst all[64], one;
    int n = discover(all, 64), rc = 0;
    if (argc > 2) { /* named instances only */
        for (int k = 2; k < argc; k++)
            if (find_inst(argv[k], &one)) rc |= cmd_install(&one, on);
            else { fprintf(stderr, "no such instance: %s\n", argv[k]); rc = 1; }
        return rc;
    }
    for (int k = 0; k < n; k++) rc |= cmd_install(&all[k], on);
    return rc;
}

static int usage(void) {
    puts("claudebar " VERSION " - Claude Code usage meter (claude + mcl instances)\n\n"
         "  claudebar                      interactive view\n"
         "  claudebar add NAME [--share]   new profile (a separate Claude login)\n"
         "  claudebar remove NAME          delete a profile\n"
         "  claudebar run NAME [args]      claude, signed in as that profile\n"
         "  claudebar gui                  window + tray icon (needs the GTK3 build)\n"
         "  claudebar status [-i NAME]     print usage  (--line: one line for panels)\n"
         "  claudebar install [NAME...]    install for this user: binary, capture, service\n"
         "                                 (NAME... hooks only those instances)\n"
         "  claudebar uninstall [NAME...]  undo it; your status line comes back exactly\n"
         "  claudebar set perfect on|off [-i NAME]   auto-start 5h windows\n"
         "  claudebar set autoupdate on|off          daily self-update by the service\n"
         "  claudebar set cost N [-i NAME]           weekly % per 5h session (0 = auto)\n"
         "  claudebar start -i NAME        start a 5h session now\n"
         "  claudebar daemon               run Perfect Use headless\n"
         "  claudebar update [--source]    install the latest release (--source: build it)");
    return 0;
}

int main(int argc, char **argv) {
    const char *c = argc > 1 ? argv[1] : "";
    Inst i;
    signal(SIGPIPE, SIG_IGN);
    if (!*c) return cmd_tui();
    if (!strcmp(c, "statusline")) return cmd_statusline(argc > 3 && !strcmp(argv[2], "-i") ? argv[3] : "default");
    if (!strcmp(c, "status")) { auto_capture(); return cmd_status(argc - 2, argv + 2); }
    if (!strcmp(c, "install")) return argc > 2 ? each(argc, argv, 1) : cmd_system(1);
    if (!strcmp(c, "uninstall")) return argc > 2 ? each(argc, argv, 0) : cmd_system(0);
    if (!strcmp(c, "set")) return cmd_set(argc - 2, argv + 2) == 2 ? usage() : 0;
    if (!strcmp(c, "add")) return cmd_add(argc - 2, argv + 2);
    if (!strcmp(c, "remove")) return cmd_remove(argc - 2, argv + 2);
    if (!strcmp(c, "run")) return cmd_run(argc - 2, argv + 2);
    if (!strcmp(c, "gui")) return cmd_gui();
    if (!strcmp(c, "daemon")) return cmd_daemon();
    if (!strcmp(c, "update")) return cmd_update(argc - 2, argv + 2);
    if (!strcmp(c, "start") && argc > 3 && find_inst(argv[3], &i)) return !perfect_start(&i);
    if (!strcmp(c, "version")) { puts(VERSION); return 0; }
    usage();
    return strcmp(c, "help") && strcmp(c, "-h") && strcmp(c, "--help");
}
