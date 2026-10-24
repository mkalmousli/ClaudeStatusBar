/* `claudebar update` installs the prebuilt binaries from the latest GitHub release;
 * `--source` pulls the repository and builds it instead. */
#include "cb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define FAIL(...) do { if (!q) fprintf(stderr, __VA_ARGS__); unlink(tmp); unlink(sum); return 1; } while (0)

/* Download one asset, check it, run it once, then swap it in atomically. */
static int pull(const char *base, const char *tag, const char *asset, const char *dest, const char *check, int q) {
    char url[400], tmp[640], sum[660], c[700], want[96] = "";
    snprintf(tmp, sizeof tmp, "%s.new", dest);
    snprintf(sum, sizeof sum, "%s.sha256", tmp);
    snprintf(url, sizeof url, "%s/releases/download/%s/%s-%s", base, tag, asset, platform());
    if (fetch(url, tmp)) FAIL("update: no prebuilt %s for %s in %s (try: claudebar update --source)\n", asset, platform(), tag);
    snprintf(c, sizeof c, "%s.sha256", url);
    char *t = fetch(c, sum) ? NULL : readfile(sum, NULL);
    if (t) sscanf(t, "%95s", want);
    free(t);
    if (!sha_ok(tmp, want)) FAIL("update: %s checksum mismatch, nothing changed\n", asset);
    chmod(tmp, 0755);
    snprintf(c, sizeof c, "'%s' %s >/dev/null 2>&1", tmp, check);
    if (system(c)) FAIL("update: downloaded %s does not run, nothing changed\n", asset);
    if (rename(tmp, dest)) FAIL("update: cannot replace %s\n", dest);
    unlink(sum);
    return 0;
}

/* 0 up to date, 1 failed, 2 updated. The GUI is refreshed too when it is installed. */
int do_update(int q) {
    char tag[64], gui[640];
    const char *base = getenv("CLAUDEBAR_REPO") ? getenv("CLAUDEBAR_REPO") : REPO_URL;
    if (!latest_tag(base, tag, sizeof tag)) { if (!q) fprintf(stderr, "update: cannot reach GitHub\n"); return 1; }
    if (!vnewer(tag, VERSION)) { if (!q) printf("up to date (%s)\n", VERSION); return 0; }
    if (pull(base, tag, "claudebar", bin_path(), "version", q)) return 1;
    sibling(gui, sizeof gui, bin_path(), "claudebar-gui");
    if (access(gui, X_OK) == 0) pull(base, tag, "claudebar-gui", gui, "--version", q);
    if (!q) printf("updated %s -> %s\n", VERSION, tag);
    return 2;
}

int cmd_update(int argc, char **argv) {
    if (argc > 0 && !strcmp(argv[0], "--source")) return source_update();
    return do_update(0) == 1;
}
