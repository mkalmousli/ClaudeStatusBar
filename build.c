/* cc build.c -o build && ./build [build|install|test|clean]
 * Incremental and parallel; needs only a C compiler (GTK3 adds claudebar-gui).
 * Env: CC, CFLAGS, LDFLAGS, OUT. */
#include "build.h"

/* Compile stale files in parallel; any failure fails the build. */
static int compile(void) {
    int running = 0, bad = 0, jobs = (int)sysconf(_SC_NPROCESSORS_ONLN);
    for (int i = 0; i < ns; i++) {
        char o[300];
        obj(srcs[i], o, sizeof o);
        if (mtime(o) > mtime(srcs[i]) && mtime(o) > mtime("src/cb.h")) continue;
        if (running >= (jobs > 0 ? jobs : 1)) { int st; wait(&st); running--; bad |= st != 0; }
        if (fork() == 0) {
            printf("  cc %s\n", srcs[i]);
            _exit(run("%s -O2 -std=gnu11 -Wall -Wextra -Wno-deprecated-declarations -Isrc %s %s -c %s -o %s",
                      cc, cflags, is_gui(srcs[i]) ? gtkc : "", srcs[i], o) != 0);
        }
        running++;
    }
    for (int st; running--; ) { wait(&st); bad |= st != 0; }
    return bad;
}

/* Object list for one program: 0 claudebar, 1 tests (no main), 2 claudebar-gui. */
static void objects(char *list, size_t n, int mode) {
    list[0] = 0;
    for (int i = 0; i < ns; i++) {
        char o[300];
        obj(srcs[i], o, sizeof o);
        if (mode != 2 && is_gui(srcs[i])) continue;
        if (mode && !strcmp(srcs[i], "src/main.c")) continue;
        snprintf(list + strlen(list), n - strlen(list), " %s", o);
    }
}

static int build(void) {
    char objs[4096];
    run("mkdir -p %s", out);
    pkg("--cflags", gtkc, sizeof gtkc);
    pkg("--libs", gtkl, sizeof gtkl);
    scan("src"), scan("gui");
    if (compile()) return 1;
    objects(objs, sizeof objs, 0);
    if (run("%s -o %s/claudebar%s %s", cc, out, objs, ldflags)) return 1;
    objects(objs, sizeof objs, 2);
    return gtkc[0] ? run("%s -o %s/claudebar-gui%s %s %s -ldl -lm", cc, out, objs, ldflags, gtkl) : 0;
}

static int test(void) {
    char objs[4096];
    int rc = build();
    DIR *d = opendir("tests");
    struct dirent *e;
    objects(objs, sizeof objs, 1);
    while (!rc && d && (e = readdir(d))) {
        int l = (int)strlen(e->d_name) - 2;
        if (!strncmp(e->d_name, "t_", 2) && l > 2 && !strcmp(e->d_name + l, ".c"))
            rc |= run("%s -std=gnu11 -Isrc %s tests/%s%s -o %s/%.*s %s && %s/%.*s", cc, cflags, e->d_name, objs, out, l, e->d_name, ldflags, out, l, e->d_name);
    }
    return rc;
}

int main(int argc, char **argv) {
    const char *c = argc > 1 ? argv[1] : "build";
    cc = env("CC", cc); out = env("OUT", out); cflags = env("CFLAGS", ""); ldflags = env("LDFLAGS", "");
    if (!strcmp(c, "clean")) return run("rm -rf %s", out);
    if (!strcmp(c, "test")) return test();
    if (build()) return 1;
    return !strcmp(c, "install") ? run("%s/claudebar install", out) : 0;
}
