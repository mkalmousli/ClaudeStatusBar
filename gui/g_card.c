/* One card per profile: name, account, the two meters, and a small menu. */
#include "g_gui.h"

static int busy; /* true while we set widgets ourselves, so handlers stay quiet */

static Row *rowk(gpointer d) { int k = GPOINTER_TO_INT(d); return k < nrows ? &rows[k] : NULL; }

static void on_start(GtkMenuItem *i, gpointer d) {
    Row *r = rowk(d);
    (void)i;
    if (r) perfect_start(&r->i);
}

static void on_auto(GtkCheckMenuItem *i, gpointer d) {
    Row *r = rowk(d);
    if (busy || !r) return;
    r->c.perfect = gtk_check_menu_item_get_active(i);
    cfg_save(r->i.key, &r->c);
}

static void on_login(GtkWidget *b, gpointer d) {
    Row *r = rowk(d);
    (void)b;
    if (r && !term_run(r->i.label)) note_box(win_window(), "No terminal found. Run this yourself:\n\nclaudebar run <profile>");
}

static void on_remove(GtkMenuItem *i, gpointer d) { (void)i; remove_dialog(win_window(), GPOINTER_TO_INT(d)); }

static GtkWidget *cell(GtkWidget *g, int x, int y, int w) {
    GtkWidget *l = gtk_label_new("");
    gtk_label_set_xalign(GTK_LABEL(l), 0);
    gtk_label_set_line_wrap(GTK_LABEL(l), TRUE);
    gtk_label_set_max_width_chars(GTK_LABEL(l), 10 * w);
    gtk_grid_attach(GTK_GRID(g), l, x, y, w, 1);
    return l;
}

static void meter_row(GtkWidget *g, const char *name, int y, GtkWidget **m, GtkWidget **l) {
    gtk_label_set_text(GTK_LABEL(cell(g, 0, y, 1)), name);
    *m = meter_new();
    gtk_grid_attach(GTK_GRID(g), *m, 1, y, 1, 1);
    *l = cell(g, 2, y, 1);
    gtk_label_set_width_chars(GTK_LABEL(*l), 24);
}

static GtkWidget *entry(GtkWidget *menu, GtkWidget *i, const char *sig, GCallback cb, int k) {
    g_signal_connect(i, sig, cb, GINT_TO_POINTER(k));
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), i);
    return i;
}

void card_build(Card *c, int k, GtkWidget *parent) {
    GtkWidget *f = gtk_frame_new(NULL), *g = gtk_grid_new(), *menu = gtk_menu_new(), *mb = gtk_menu_button_new();
    snprintf(c->key, sizeof c->key, "%s", rows[k].i.key);
    gtk_container_set_border_width(GTK_CONTAINER(g), 14);
    gtk_grid_set_row_spacing(GTK_GRID(g), 8), gtk_grid_set_column_spacing(GTK_GRID(g), 12);
    c->title = cell(g, 0, 0, 2);
    c->sub = cell(g, 0, 1, 2);
    meter_row(g, "5h", 2, &c->m5, &c->l5);
    meter_row(g, "Week", 3, &c->mw, &c->lw);
    c->status = cell(g, 0, 4, 2);
    c->login = gtk_button_new_with_label("Sign in");
    gtk_widget_set_no_show_all(c->login, TRUE);
    g_signal_connect(c->login, "clicked", G_CALLBACK(on_login), GINT_TO_POINTER(k));
    gtk_grid_attach(GTK_GRID(g), c->login, 2, 4, 1, 1);
    entry(menu, gtk_menu_item_new_with_label("Start a session now"), "activate", G_CALLBACK(on_start), k);
    c->auto_item = entry(menu, gtk_check_menu_item_new_with_label("Start sessions automatically"), "toggled", G_CALLBACK(on_auto), k);
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), gtk_separator_menu_item_new());
    gtk_widget_set_sensitive(entry(menu, gtk_menu_item_new_with_label("Remove profile…"), "activate", G_CALLBACK(on_remove), k), rows[k].i.mcl);
    gtk_widget_show_all(menu);
    gtk_container_add(GTK_CONTAINER(mb), gtk_image_new_from_icon_name("view-more-symbolic", GTK_ICON_SIZE_BUTTON));
    gtk_menu_button_set_popup(GTK_MENU_BUTTON(mb), menu);
    gtk_widget_set_valign(mb, GTK_ALIGN_START);
    gtk_button_set_relief(GTK_BUTTON(mb), GTK_RELIEF_NONE);
    gtk_grid_attach(GTK_GRID(g), mb, 2, 0, 1, 2);
    gtk_container_add(GTK_CONTAINER(f), g);
    gtk_box_pack_start(GTK_BOX(parent), f, FALSE, FALSE, 0);
}

/* The menu follows the saved state. */
void card_sync(Card *c, const Row *r) {
    busy = 1;
    gtk_check_menu_item_set_active(GTK_CHECK_MENU_ITEM(c->auto_item), r->c.perfect);
    busy = 0;
}
