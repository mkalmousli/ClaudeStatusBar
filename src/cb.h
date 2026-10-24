/* claudebar: shared declarations. POSIX only (Linux, macOS, BSD). */
#ifndef CB_H
#define CB_H
#include <stddef.h>
#define VERSION "1.0.0"
#define REPO_URL "https://github.com/mkalmousli/ClaudeStatusBar"
#define H5 18000L
#define WK 604800L

typedef struct { long ts, h5r, wkr, ht; double h5, wk, cost, ctx;
                 char sid[65], model[64], cwd[160]; } Snap; /* h5/wk < 0: unknown */
typedef struct { long t, hr, wr; double h, w; } Point;
typedef struct { char key[80], label[64], dir[512]; int mcl; } Inst;
typedef struct { int perfect, has_orig, mcl_flag, optout; double cost;
                 char chain[1024], orig[1024]; } ICfg;
typedef struct { Snap *s; int ns; Point *p; int np; } Data;
typedef struct { int h5ok, wkok, src, clock_limited, pace; double h5, wk, burn,
                 left, wend, waste, gap; long h5r, wkr, newest, crit_in; } View;

/* util.c */
long now_s(void);
void dur(long s, char *o, size_t n);
void clock_str(long ts, char *o, size_t n);
const char *root(void);
void mkdirs(const char *path);
char *readfile(const char *path, size_t *len);
int writefile(const char *path, const char *buf, size_t len);
char *readall(int fd, size_t *len);
/* json.c, jedit.c: a scanner over raw text; values are pointers into it */
const char *jskip(const char *p);
const char *jlocate(const char *obj, const char *key, const char **kstart);
const char *jpath(const char *json, const char *path);
double jnum(const char *v, double def);
int jstr(const char *v, char *out, size_t n);
char *jset(const char *json, const char *key, const char *raw);
char *jdel(const char *json, const char *key);
/* store.c */
void record(const char *key, const char *json);
int snap_parse(char *line, Snap *s);
void load(const char *key, Data *d, long now);
void data_free(Data *d);
/* model.c, burn.c */
void build_view(const Data *d, long now, double cost_override, View *v);
double burn_rate(const Data *d, long wkr, double wk, long now, int *src);
/* inst.c, config.c */
int discover(Inst *out, int max);
int find_inst(const char *name, Inst *out);
void account(const Inst *i, char *out, size_t n);
void cfg_load(const char *key, ICfg *c);
void cfg_save(const char *key, const ICfg *c);
/* actions */
int cmd_install(const Inst *i, int on);
int cmd_statusline(const char *key);
void perfect_tick(const Inst *i);
int perfect_start(const Inst *i);
void notify(const char *title, const char *body);
int cmd_daemon(void);
int cmd_update(int argc, char **argv);
int do_update(int quiet);
int source_update(void);
/* sysinst.c, service.c, fetch.c: the user-system side */
extern int quiet;
const char *bin_path(void);
void auto_capture(void);
int cmd_system(int on);
int service(int on);
const char *platform(void);
int fetch(const char *url, const char *out);
int sha_ok(const char *file, const char *want);
int latest_tag(const char *base, char *out, size_t n);
int vnewer(const char *a, const char *b);
int autoupdate(void);
void autoupdate_set(int on);
int cmd_status(int argc, char **argv);
int cmd_set(int argc, char **argv);
/* profile.c: add, remove, run */
const char *profile_add(const char *name, int share);
const char *profile_remove(const Inst *i);
int cmd_add(int argc, char **argv);
int cmd_remove(int argc, char **argv);
int cmd_run(int argc, char **argv);
/* desktop.c: GUI binary, menu entry, autostart */
void sibling(char *o, size_t n, const char *exe, const char *name);
int desktop(int on);
int cmd_gui(void);
/* tui */
typedef struct { Inst i; ICfg c; Data d; View v; char acct[96]; int installed; } Row;
extern Row rows[];
extern int nrows, sel, detail;
extern const char *pace_name[];
void rows_reload(void);
extern char msg[];
void term_raw(int on);
int term_key(int ms);
void draw(void);
int cmd_tui(void);
#endif
