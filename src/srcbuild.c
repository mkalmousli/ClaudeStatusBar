/* Optional: update by building the repository yourself (needs git and cc). */
#include "cb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int sh(const char *fmt, const char *a) {
    char c[1400];
    snprintf(c, sizeof c, fmt, a, a);
    return system(c);
}

int source_update(void) {
    char src[600];
    snprintf(src, sizeof src, "%s/src", root());
    mkdirs(root());
    int rc = access(src, F_OK) == 0 ? sh("git -C '%s' pull --ff-only -q", src)
                                    : sh("git clone -q --depth 1 " REPO_URL ".git '%s'", src);
    if (rc) { fprintf(stderr, "update: git failed (is git installed?)\n"); return 1; }
    if (sh("cd '%s' && cc build.c -o build && ./build && ./out/claudebar install >/dev/null", src)) {
        fprintf(stderr, "update: build failed\n");
        return 1;
    }
    puts("updated from source");
    return 0;
}
