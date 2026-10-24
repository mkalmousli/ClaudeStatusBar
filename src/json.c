/* A scanner, not a parser: finds values inside raw JSON text without copying. */
#include "cb.h"
#include <ctype.h>
#include <stdlib.h>
#include <string.h>

static const char *ws(const char *p) { while (*p && isspace((unsigned char)*p)) p++; return p; }

static const char *skip_str(const char *p) {
    for (p++; *p && *p != '"'; p++)
        if (*p == '\\' && p[1]) p++;
    return *p ? p + 1 : p;
}

/* End of the value that starts at p (after optional whitespace). */
const char *jskip(const char *p) {
    p = ws(p);
    if (*p == '"') return skip_str(p);
    if (*p == '{' || *p == '[') {
        for (int depth = 0; *p; ) {
            if (*p == '"') { p = skip_str(p); continue; }
            if (*p == '{' || *p == '[') depth++;
            if (*p == '}' || *p == ']') depth--;
            p++;
            if (!depth) break;
        }
        return p;
    }
    while (*p && !strchr(",}] \t\r\n", *p)) p++;
    return p;
}

/* Value of `key` in the object at obj; *kstart is where the key's quote sits. */
const char *jlocate(const char *obj, const char *key, const char **kstart) {
    const char *p = ws(obj);
    size_t kl = strlen(key);
    if (*p != '{') return NULL;
    for (p = ws(p + 1); *p == '"'; p = ws(p)) {
        const char *ks = p, *ke = skip_str(p), *v;
        p = ws(ke);
        if (*p != ':') return NULL;
        v = ws(p + 1);
        if ((size_t)(ke - ks) == kl + 2 && !strncmp(ks + 1, key, kl)) {
            if (kstart) *kstart = ks;
            return v;
        }
        p = ws(jskip(v));
        if (*p == ',') p++;
    }
    return NULL;
}

/* "a.b.c" walks nested objects. */
const char *jpath(const char *json, const char *path) {
    char part[64];
    const char *v = json;
    while (v && *path) {
        size_t n = strcspn(path, ".");
        if (n >= sizeof part) return NULL;
        memcpy(part, path, n);
        part[n] = 0;
        v = jlocate(v, part, NULL);
        path += n + (path[n] == '.');
    }
    return v;
}

double jnum(const char *v, double def) {
    if (!v || !(isdigit((unsigned char)*v) || *v == '-')) return def;
    return strtod(v, NULL);
}

/* Copy a string value, decoding the common escapes. */
int jstr(const char *v, char *out, size_t n) {
    size_t o = 0;
    if (!v || *v != '"' || !n) return 0;
    for (v++; *v && *v != '"' && o + 1 < n; v++) {
        if (*v == '\\' && v[1]) {
            v++;
            out[o++] = *v == 'n' ? '\n' : *v == 't' ? '\t' : *v;
        } else out[o++] = *v;
    }
    out[o] = 0;
    return 1;
}
