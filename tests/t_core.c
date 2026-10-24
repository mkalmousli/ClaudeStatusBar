#include "cb.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>

int main(void) {
    const char *j = "{\"a\":{\"b\":[1,{\"x\":\"}\"}],\"c\":42.5},\"d\":\"s\\\"q\"}";
    assert(jnum(jpath(j, "a.c"), 0) == 42.5);
    char s[16];
    assert(jstr(jpath(j, "d"), s, sizeof s) && !strcmp(s, "s\"q"));
    assert(!jpath(j, "a.zz"));
    char *e = jset("{}", "k", "1");
    assert(jnum(jpath(e, "k"), 0) == 1);
    char *f = jset(e, "k", "2"), *g = jdel(f, "k");
    assert(jnum(jpath(f, "k"), 0) == 2 && !jpath(g, "k"));
    char *h = jdel("{\"a\":1,\"b\":2}", "b");
    assert(jnum(jpath(h, "a"), 0) == 1 && !jpath(h, "b"));
    /* model: 60% elapsed, 10% used => gap 50 => "wasting allowance" */
    long now = 1000000;
    Snap sn = {.ts = now, .h5 = 10, .wk = 5, .h5r = now + 2 * 3600, .wkr = now + 12 * 3600};
    Data d = {.s = &sn, .ns = 1};
    View v;
    build_view(&d, now, 17, &v);
    assert(v.h5ok && v.pace == 2 && v.burn == 17 && v.src == 3);
    assert(v.clock_limited && v.left == 2 && v.waste > 0); /* 10h spare = 2 windows */
    assert(vnewer("v2.1.0", "2.0.9") && !vnewer("2.0.0", "2.0.0") && !vnewer("1.9.9", "2.0.0"));
    assert(strchr(platform(), '-'));
    puts("core ok");
    return 0;
}
