/* The tray icon. StatusNotifier covers KDE, Xfce, GNOME (with its extension), Cinnamon, MATE,
 * LXQt, sway, waybar...; GtkStatusIcon (XEmbed) covers older panels. With neither, the
 * window just stays a window. */
#include "g_gui.h"

static void *ind;
static GtkStatusIcon *si;
static GtkWidget *menu, *info[8];
static char dir[600];

int tray_ok(void) { return (ind && sni_watcher()) || (si && gtk_status_icon_is_embedded(si)); }

static void on_open(GtkMenuItem *i, gpointer d) { (void)i, (void)d; win_show(0); }
static void on_quit(GtkMenuItem *i, gpointer d) { (void)i, (void)d; g_application_quit(g_application_get_default()); }
static void on_click(GtkStatusIcon *i, gpointer d) { (void)i, (void)d; win_show(1); }
static void on_popup(GtkStatusIcon *i, guint b, guint t, gpointer d) {
    (void)d;
    gtk_menu_popup(GTK_MENU(menu), NULL, NULL, gtk_status_icon_position_menu, i, b, t);
}

static GtkWidget *item(const char *text, GCallback cb) {
    GtkWidget *i = gtk_menu_item_new_with_label(text);
    if (cb) g_signal_connect(i, "activate", cb, NULL); else gtk_widget_set_sensitive(i, FALSE);
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), i);
    return i;
}

void tray_init(void) {
    char p[700];
    snprintf(dir, sizeof dir, "%s/icons", root());
    snprintf(p, sizeof p, "%s/claudebar-a.png", dir);
    mkdirs(dir);
    icon_png(p, 0, 0);
    menu = gtk_menu_new();
    item("Open claudebar", G_CALLBACK(on_open));
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), gtk_separator_menu_item_new());
    for (int k = 0; k < 8; k++) { info[k] = item("", NULL); gtk_widget_set_no_show_all(info[k], TRUE); }
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), gtk_separator_menu_item_new());
    item("Quit", G_CALLBACK(on_quit));
    gtk_widget_show_all(menu);
    if ((ind = sni_open(dir, "claudebar-a", menu))) return;
    si = gtk_status_icon_new_from_file(p);
    g_signal_connect(si, "activate", G_CALLBACK(on_click), NULL);
    g_signal_connect(si, "popup-menu", G_CALLBACK(on_popup), NULL);
}

static const char *one(const View *v, int five, char *o, size_t n) {
    double x = five ? v->h5 : v->wk;
    if (five ? v->h5ok : v->wkok) snprintf(o, n, "%s %.0f%%", five ? "5h" : "wk", x);
    else snprintf(o, n, "%s --", five ? "5h" : "wk");
    return o;
}

/* The first instance with data drives the icon; every instance gets a menu line and tooltip. */
void tray_update(void) {
    static int last = -2, flip;
    char a[32], b[32], line[128], tip[600] = "", p[700], name[24];
    int pick = 0, key;
    for (int k = nrows - 1; k >= 0; k--) if (rows[k].v.h5ok) pick = k;
    for (int k = 0; k < 8; k++) {
        gtk_widget_set_visible(info[k], k < nrows);
        if (k >= nrows) continue;
        snprintf(line, sizeof line, "%s: %s · %s", rows[k].i.label, one(&rows[k].v, 1, a, sizeof a), one(&rows[k].v, 0, b, sizeof b));
        gtk_menu_item_set_label(GTK_MENU_ITEM(info[k]), line);
        snprintf(tip + strlen(tip), sizeof tip - strlen(tip), "%s%s", k ? "\n" : "", line);
    }
    if (!nrows) return;
    const View *v = &rows[pick].v;
    key = v->h5ok ? (int)(v->h5 + 0.5) : -1;
    snprintf(line, sizeof line, "%s · %s", one(v, 1, a, sizeof a), one(v, 0, b, sizeof b));
    if (si) gtk_status_icon_set_tooltip_text(si, tip);
    if (key == last) return;
    last = key;
    flip = !flip;
    snprintf(name, sizeof name, "claudebar-%c", flip ? 'b' : 'a'); /* a new name defeats icon caches */
    snprintf(p, sizeof p, "%s/%s.png", dir, name);
    icon_png(p, key >= 0, v->h5);
    if (ind) sni_set(ind, name, line);
    else if (si) gtk_status_icon_set_from_file(si, p);
}
