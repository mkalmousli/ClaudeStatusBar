/* Perfect Use: start each 5h window the moment it is free, warn when one is
 * about to be wasted. A window left unopened is weekly allowance never spent. */
#include "cb.h"
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#define MIN_GAP (H5 - 1800)  /* a real window cannot roll over faster than this */

static void detach(void) {
    int z = open("/dev/null", O_RDWR);
    dup2(z, 0); dup2(z, 1); dup2(z, 2);
    setsid();
}

/* Double fork, so nothing is left to reap: returns 0 in the detached child, 1 in the caller. */
static int spawn(void) {
    pid_t p = fork();
    if (p < 0) return -1;
    if (p == 0) { if (fork() != 0) _exit(0); detach(); return 0; }
    waitpid(p, NULL, 0);
    return 1;
}

void notify(const char *title, const char *body) {
    if (!isatty(2)) fprintf(stderr, "%s: %s\n", title, body); /* a TUI owns the tty */
    if (spawn() == 0) {
#ifdef __APPLE__
        char s[600];
        snprintf(s, sizeof s, "display notification \"%s\" with title \"%s\"", body, title);
        execlp("osascript", "osascript", "-e", s, (char *)NULL);
#else
        execlp("notify-send", "notify-send", title, body, (char *)NULL);
#endif
        _exit(127);
    }
}

int perfect_start(const Inst *i) {
    const char *m = getenv("CLAUDEBAR_MODEL");
    if (spawn() != 0) return 1;
    if (i->mcl) setenv("CLAUDE_CONFIG_DIR", i->dir, 1);
    execlp("claude", "claude", "-p", "Hi Claude", "--model", m ? m : "haiku", (char *)NULL);
    _exit(127);
}

static void pstate(const char *key, long *w, int save) {
    char p[600], b[64];
    snprintf(p, sizeof p, "%s/%s/perfect", root(), key);
    if (save) { int n = snprintf(b, sizeof b, "%ld %ld\n", w[0], w[1]); writefile(p, b, (size_t)n); return; }
    char *t = readfile(p, NULL);
    w[0] = w[1] = 0;
    if (t) sscanf(t, "%ld %ld", &w[0], &w[1]);
    free(t);
}

void perfect_tick(const Inst *i) {
    ICfg c;
    Data d;
    View v;
    long st[2], now = now_s();
    char acct[96], msg[256], left[16];
    cfg_load(i->key, &c);
    if (!c.perfect) return;
    load(i->key, &d, now);
    build_view(&d, now, c.cost, &v);
    pstate(i->key, st, 0);
    account(i, acct, sizeof acct);
    int fresh = !v.h5ok || (v.h5 == 0 && !v.h5r);
    if (fresh && d.np > 0 && *acct && now - st[0] >= MIN_GAP) {
        if (perfect_start(i)) {
            st[0] = now; pstate(i->key, st, 1);
            snprintf(msg, sizeof msg, "%s: started a new 5h session so its share of the week isn't left unspent", i->label);
            notify("Perfect Use", msg);
        }
    } else if (v.gap >= 60 && v.h5r && st[1] != v.h5r) {
        dur(v.h5r - now, left, sizeof left);
        snprintf(msg, sizeof msg, "%s: %s left in this 5h session and only %.0f%% used. Use it or lose that share of the week", i->label, left, v.h5);
        notify("Perfect Use: allowance about to be wasted", msg);
        st[1] = v.h5r; pstate(i->key, st, 1);
    }
    data_free(&d);
}
