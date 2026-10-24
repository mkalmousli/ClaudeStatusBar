/* GTK3 front end: one window and one tray icon over the same data as the terminal view. */
#ifndef G_GUI_H
#define G_GUI_H
#include <gtk/gtk.h>
#include "cb.h"

typedef struct { char key[80]; GtkWidget *title, *sub, *m5, *l5, *mw, *lw, *status, *login, *auto_item; } Card;

void rgb_set(cairo_t *c, double pct);      /* green -> red, same bands as the terminal */
const char *pct_hex(double pct);
GtkWidget *meter_new(void);
void meter_set(GtkWidget *m, int ok, double used, double elapsed);
void icon_png(const char *path, int ok, double pct);
void card_build(Card *c, int k, GtkWidget *parent);
void card_update(Card *c, int k);
void win_init(GtkApplication *app);
GtkWindow *win_window(void);
GtkWidget *app_menu(void);                  /* g_menu.c: the header menu button */
void add_dialog(GtkWindow *w);              /* g_add.c */
void remove_dialog(GtkWindow *w, int k);
void note_box(GtkWindow *w, const char *text);
int term_run(const char *profile);          /* g_term.c: a terminal running `claudebar run NAME` */
void win_show(int toggle);
void win_update(void);
int sni_watcher(void);
void *sni_open(const char *dir, const char *icon, GtkWidget *menu);
void sni_set(void *ind, const char *icon, const char *label);
void tray_init(void);
void tray_update(void);
int tray_ok(void);
#endif
