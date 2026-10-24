/* Helpers for build.c: running commands, finding sources, object paths. */
#include <dirent.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static char *srcs[64];
static int ns;
static const char *cc = "cc", *out = "out", *cflags = "", *ldflags = "";
static char gtkc[2048], gtkl[2048]; /* empty when GTK3 is not installed: no GUI then */

static const char *env(const char *k, const char *d) { return getenv(k) ? getenv(k) : d; }

static int run(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static int run(const char *fmt, ...) {
    char c[4096];
    va_list a;
    va_start(a, fmt);
    vsnprintf(c, sizeof c, fmt, a);
    va_end(a);
    return system(c);
}

static time_t mtime(const char *p) { struct stat s; return stat(p, &s) ? 0 : s.st_mtime; }

/* GUI sources are gui/g_*.c: they are only built when GTK3 is there. */
static int is_gui(const char *src) { return strstr(src, "gui/g_") != NULL; }

static void pkg(const char *flag, char *buf, size_t n) {
    char c[100];
    snprintf(c, sizeof c, "pkg-config %s gtk+-3.0 2>/dev/null", flag);
    FILE *p = popen(c, "r");
    buf[0] = 0;
    if (p && fgets(buf, (int)n, p)) buf[strcspn(buf, "\n")] = 0;
    if (p) pclose(p);
}

static void scan(const char *dir) {
    DIR *d = opendir(dir);
    struct dirent *e;
    while (d && (e = readdir(d)) && ns < 64) {
        size_t l = strlen(e->d_name);
        char p[300];
        snprintf(p, sizeof p, "%s/%s", dir, e->d_name);
        if (l > 2 && !strcmp(e->d_name + l - 2, ".c") && (gtkc[0] || !is_gui(p))) srcs[ns++] = strdup(p);
    }
    if (d) closedir(d);
}

static void obj(const char *src, char *o, size_t n) {
    snprintf(o, n, "%s/%s", out, strrchr(src, '/') + 1);
    o[strlen(o) - 1] = 'o';
}
