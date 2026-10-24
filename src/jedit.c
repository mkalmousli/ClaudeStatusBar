/* Edit raw JSON text in place, so a user's formatting and key order survive. */
#include "cb.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *splice(const char *s, size_t a, size_t b, const char *ins) {
    size_t il = strlen(ins), tl = strlen(s);
    char *r = malloc(tl - (b - a) + il + 1);
    if (!r) return NULL;
    memcpy(r, s, a);
    memcpy(r + a, ins, il);
    strcpy(r + a + il, s + b);
    return r;
}

/* Set top-level `key` to the raw JSON `raw`, replacing or inserting it. */
char *jset(const char *json, const char *key, const char *raw) {
    const char *ks, *v = jlocate(json, key, &ks);
    if (v) return splice(json, (size_t)(v - json), (size_t)(jskip(v) - json), raw);
    const char *o = json;
    while (*o && isspace((unsigned char)*o)) o++;
    if (*o != '{') return NULL;
    const char *rest = o + 1;
    while (isspace((unsigned char)*rest)) rest++;
    char ins[2048];
    snprintf(ins, sizeof ins, "\n  \"%s\": %s%s", key, raw, *rest == '}' ? "\n" : ",");
    return splice(json, (size_t)(o + 1 - json), (size_t)(o + 1 - json), ins);
}

/* Remove top-level `key` together with one neighbouring comma. */
char *jdel(const char *json, const char *key) {
    const char *ks, *v = jlocate(json, key, &ks);
    if (!v) return strdup(json);
    const char *e = jskip(v), *n = e;
    while (isspace((unsigned char)*n)) n++;
    size_t a = (size_t)(ks - json), b = (size_t)(e - json);
    if (*n == ',') b = (size_t)(n + 1 - json);
    else while (a > 0 && isspace((unsigned char)json[a - 1])) a--, (void)0;
    if (*n != ',' && a > 0 && json[a - 1] == ',') a--;
    return splice(json, a, b, "");
}
