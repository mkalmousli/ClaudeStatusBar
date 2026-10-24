/* A user service (no root): systemd on Linux, launchd on macOS. */
#include "cb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifdef __APPLE__
#define SVC "Library/LaunchAgents/io.github.mkalmousli.claudebar.plist"
#define ON "launchctl unload '%s' 2>/dev/null; launchctl load '%s'"
#define OFF "launchctl unload '%s'"
#define BODY "<?xml version=\"1.0\"?><plist version=\"1.0\"><dict><key>Label</key>" \
    "<string>io.github.mkalmousli.claudebar</string><key>ProgramArguments</key><array>" \
    "<string>%s</string><string>daemon</string></array><key>RunAtLoad</key><true/>" \
    "<key>KeepAlive</key><true/></dict></plist>\n"
#else
#define SVC ".config/systemd/user/claudebar.service"
/* %.0s eats the path arguments the launchd variant uses */
#define ON "systemctl --user daemon-reload && systemctl --user enable --now claudebar.service%.0s%.0s"
#define OFF "systemctl --user disable --now claudebar.service%.0s"
#define BODY "[Unit]\nDescription=claudebar: Perfect Use, auto capture, auto update\n\n" \
    "[Service]\nExecStart=%s daemon\nRestart=always\nRestartSec=10\n\n" \
    "[Install]\nWantedBy=default.target\n"
#endif

/* Returns 1 when the service is in place, 0 when this system cannot run one. */
int service(int on) {
    char path[600], body[1200], cmd[1400], *slash;
    snprintf(path, sizeof path, "%s/" SVC, getenv("HOME") ? getenv("HOME") : ".");
    if (!on) {
        snprintf(cmd, sizeof cmd, OFF " >/dev/null 2>&1", path);
        int rc = system(cmd);
        unlink(path);
        return rc == 0;
    }
    slash = strrchr(path, '/');
    *slash = 0;
    mkdirs(path);
    *slash = '/';
    int n = snprintf(body, sizeof body, BODY, bin_path());
    if (writefile(path, body, (size_t)n)) return 0;
    snprintf(cmd, sizeof cmd, ON " >/dev/null 2>&1", path, path);
    return system(cmd) == 0;
}
