/* The window: a header with Add and a menu, then a card per profile. Cards are rebuilt
 * only when the set of profiles changes. */
#include "g_gui.h"

static GtkWidget *win, *box;
static Card cards[64];
static int ncards = -1;

GtkWindow *win_window(void) { return GTK_WINDOW(win); }

static int same(void) {
    if (ncards != nrows) return 0;
    for (int k = 0; k < nrows; k++) if (strcmp(cards[k].key, rows[k].i.key)) return 0;
    return 1;
}

static void drop(GtkWidget *w, gpointer d) { (void)d; gtk_widget_destroy(w); }

static void rebuild(void) {
    gtk_container_foreach(GTK_CONTAINER(box), drop, NULL);
    ncards = nrows;
    for (int k = 0; k < nrows; k++) card_build(&cards[k], k, box);
    if (!nrows) gtk_box_pack_start(GTK_BOX(box), gtk_label_new("No profiles yet. Press “Add profile”."), FALSE, FALSE, 40);
    gtk_widget_show_all(box);
}

void win_update(void) {
    if (!win) return;
    if (!same()) rebuild();
    for (int k = 0; k < ncards; k++) card_update(&cards[k], k);
}

static gboolean closing(GtkWidget *w, GdkEvent *e, gpointer d) {
    (void)e, (void)d;
    if (tray_ok()) { gtk_widget_hide(w); return TRUE; } /* the tray icon keeps running */
    g_application_quit(g_application_get_default());
    return FALSE;
}

static void on_add(GtkButton *b, gpointer d) { (void)b, (void)d; add_dialog(GTK_WINDOW(win)); }

void win_init(GtkApplication *app) {
    GtkWidget *hb = gtk_header_bar_new(), *add = gtk_button_new_with_label("Add profile"), *sc = gtk_scrolled_window_new(NULL, NULL);
    win = gtk_application_window_new(app);
    gtk_window_set_default_size(GTK_WINDOW(win), 560, 520);
    gtk_header_bar_set_title(GTK_HEADER_BAR(hb), "claudebar");
    gtk_header_bar_set_show_close_button(GTK_HEADER_BAR(hb), TRUE);
    gtk_button_set_image(GTK_BUTTON(add), gtk_image_new_from_icon_name("list-add-symbolic", GTK_ICON_SIZE_BUTTON));
    gtk_button_set_always_show_image(GTK_BUTTON(add), TRUE);
    g_signal_connect(add, "clicked", G_CALLBACK(on_add), NULL);
    gtk_header_bar_pack_start(GTK_HEADER_BAR(hb), add);
    gtk_header_bar_pack_end(GTK_HEADER_BAR(hb), app_menu());
    gtk_window_set_titlebar(GTK_WINDOW(win), hb);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(sc), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(sc), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 12);
    gtk_container_set_border_width(GTK_CONTAINER(box), 14);
    gtk_container_add(GTK_CONTAINER(sc), box);
    gtk_container_add(GTK_CONTAINER(win), sc);
    g_signal_connect(win, "delete-event", G_CALLBACK(closing), NULL);
}

void win_show(int toggle) {
    if (toggle && gtk_widget_get_visible(win)) gtk_widget_hide(win);
    else { gtk_widget_show_all(win); gtk_window_present(GTK_WINDOW(win)); }
}
