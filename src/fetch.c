/* Talking to GitHub with curl or wget: no libraries, nothing to link. */
#include "cb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Release asset names: claudebar-<os>-<arch>, built by the release workflow. */
const char *platform(void) {
#if defined(__APPLE__)
#define OS "macos"
#elif defined(__FreeBSD__)
#define OS "freebsd"
#else
#define OS "linux"
#endif
#if defined(__x86_64__)
#define ARCH "x86_64"
#elif defined(__aarch64__)
#define ARCH "aarch64"
#elif defined(__arm__)
#define ARCH "armv7"
#elif defined(__i386__)
#define ARCH "i686"
#elif defined(__riscv) && __riscv_xlen == 64
#define ARCH "riscv64"
#elif defined(__powerpc64__)
#define ARCH "ppc64le"
#elif defined(__s390x__)
#define ARCH "s390x"
#else
#define ARCH "unknown"
#endif
    return OS "-" ARCH;
}

int fetch(const char *url, const char *out) {
    char c[1500];
    snprintf(c, sizeof c, "(curl -fsSL --retry 2 -o '%s' '%s' || wget -qO '%s' '%s') >/dev/null 2>&1", out, url, out, url);
    return system(c);
}

int sha_ok(const char *file, const char *want) {
    char c[700], got[96] = "";
    snprintf(c, sizeof c, "(sha256sum '%s' || shasum -a 256 '%s') 2>/dev/null", file, file);
    FILE *p = popen(c, "r");
    if (p && fscanf(p, "%95s", got) != 1) got[0] = 0;
    if (p) pclose(p);
    return strlen(want) == 64 && !strcmp(got, want);
}

/* GitHub redirects /releases/latest to /releases/tag/<tag>: no API, no rate limit. */
int latest_tag(const char *base, char *out, size_t n) {
    char c[600], url[400] = "";
    snprintf(c, sizeof c, "curl -fsSL -o /dev/null -w '%%{url_effective}' '%s/releases/latest' 2>/dev/null", base);
    FILE *p = popen(c, "r");
    if (p && !fgets(url, sizeof url, p)) url[0] = 0;
    if (p) pclose(p);
    char *t = strstr(url, "/tag/");
    if (!t) return 0;
    snprintf(out, n, "%s", t + 5);
    return 1;
}

int vnewer(const char *a, const char *b) {
    int x[3] = {0}, y[3] = {0};
    sscanf(*a == 'v' ? a + 1 : a, "%d.%d.%d", &x[0], &x[1], &x[2]);
    sscanf(*b == 'v' ? b + 1 : b, "%d.%d.%d", &y[0], &y[1], &y[2]);
    for (int k = 0; k < 3; k++) if (x[k] != y[k]) return x[k] > y[k];
    return 0;
}
