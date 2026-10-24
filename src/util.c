#include "cb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>

long now_s(void) { return (long)time(NULL); }

void dur(long s, char *o, size_t n) {
    if (s < 0) s = 0;
    if (s < 60) snprintf(o, n, "%lds", s);
    else if (s < 3600) snprintf(o, n, "%ldm", s / 60);
    else if (s < 86400) snprintf(o, n, "%ldh%02ldm", s / 3600, s % 3600 / 60);
    else snprintf(o, n, "%ldd%02ldh", s / 86400, s % 86400 / 3600);
}

/* Local wall-clock; adds the weekday when the time is not today. */
void clock_str(long ts, char *o, size_t n) {
    time_t t = ts, cur = time(NULL);
    struct tm a, b;
    localtime_r(&t, &a);
    localtime_r(&cur, &b);
    strftime(o, n, a.tm_yday == b.tm_yday && a.tm_year == b.tm_year ? "%H:%M" : "%a %H:%M", &a);
}

/* Everything lives under one directory: $CLAUDEBAR_HOME, XDG data, or ~/.local/share. */
const char *root(void) {
    static char p[512];
    const char *h = getenv("CLAUDEBAR_HOME"), *x = getenv("XDG_DATA_HOME");
    if (h) snprintf(p, sizeof p, "%s", h);
    else if (x && *x) snprintf(p, sizeof p, "%s/claudebar", x);
    else snprintf(p, sizeof p, "%s/.local/share/claudebar", getenv("HOME") ? getenv("HOME") : ".");
    return p;
}

void mkdirs(const char *path) {
    char b[600];
    snprintf(b, sizeof b, "%s", path);
    for (char *p = b + 1; *p; p++)
        if (*p == '/') { *p = 0; mkdir(b, 0755); *p = '/'; }
    mkdir(b, 0755);
}

char *readall(int fd, size_t *len) {
    size_t cap = 4096, n = 0;
    char *b = malloc(cap + 1);
    ssize_t r;
    while (b && (r = read(fd, b + n, cap - n)) > 0) {
        n += (size_t)r;
        if (n == cap) b = realloc(b, (cap *= 2) + 1);
    }
    if (!b) return NULL;
    b[n] = 0;
    if (len) *len = n;
    return b;
}

char *readfile(const char *path, size_t *len) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return NULL;
    char *b = readall(fd, len);
    close(fd);
    return b;
}

/* Temp file + rename: readers never see a torn file; keeps an existing mode. */
int writefile(const char *path, const char *buf, size_t len) {
    char tmp[640];
    struct stat st;
    snprintf(tmp, sizeof tmp, "%s.tmp%d", path, (int)getpid());
    int fd = open(tmp, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return -1;
    if (stat(path, &st) == 0) fchmod(fd, st.st_mode & 0777);
    int ok = write(fd, buf, len) == (ssize_t)len;
    close(fd);
    if (!ok || rename(tmp, path) != 0) { unlink(tmp); return -1; }
    return 0;
}
