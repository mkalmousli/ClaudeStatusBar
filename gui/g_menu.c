/* The header menu: updates, about, quit. */
#include "g_gui.h"

static GtkWidget *check;

static gboolean done(gpointer d) {
    int r = GPOINTER_TO_INT(d) - 1;
    gtk_widget_set_sensitive(check, TRUE);
    note_box(win_window(), r == 0 ? "claudebar is up to date." : r == 2 ? "Updated. Restart claudebar to use the new version."
                                                                       : "Could not check for updates.");
    return FALSE;
}

static gpointer worker(gpointer d) { (void)d; g_idle_add(done, GINT_TO_POINTER(do_update(1) + 1)); return NULL; }

static void on_check(GtkMenuItem *i, gpointer d) {
    (void)d;
    gtk_widget_set_sensitive(GTK_WIDGET(i), FALSE);
    check = GTK_WIDGET(i);
    g_thread_unref(g_thread_new("update", worker, NULL));
}

static void on_auto(GtkCheckMenuItem *i, gpointer d) { (void)d; autoupdate_set(gtk_check_menu_item_get_active(i)); }
static void on_about(GtkMenuItem *i, gpointer d) {
    GtkWidget *a = gtk_about_dialog_new();
    const char *by[] = {"mkalmousli", NULL};
    (void)i, (void)d;
    gtk_about_dialog_set_program_name(GTK_ABOUT_DIALOG(a), "claudebar");
    gtk_about_dialog_set_version(GTK_ABOUT_DIALOG(a), VERSION);
    gtk_about_dialog_set_comments(GTK_ABOUT_DIALOG(a), "Usage meter for Claude Code: every profile, one place.");
    gtk_about_dialog_set_website(GTK_ABOUT_DIALOG(a), REPO_URL);
    gtk_about_dialog_set_license_type(GTK_ABOUT_DIALOG(a), GTK_LICENSE_GPL_3_0);
    gtk_about_dialog_set_authors(GTK_ABOUT_DIALOG(a), by);
    gtk_window_set_transient_for(GTK_WINDOW(a), win_window());
    gtk_dialog_run(GTK_DIALOG(a));
    gtk_widget_destroy(a);
}

static void on_quit(GtkMenuItem *i, gpointer d) { (void)i, (void)d; g_application_quit(g_application_get_default()); }

GtkWidget *app_menu(void) {
    GtkWidget *b = gtk_menu_button_new(), *m = gtk_menu_new(), *a = gtk_check_menu_item_new_with_label("Update automatically");
    GtkWidget *c = gtk_menu_item_new_with_label("Check for updates"), *ab = gtk_menu_item_new_with_label("About"), *q = gtk_menu_item_new_with_label("Quit");
    gtk_check_menu_item_set_active(GTK_CHECK_MENU_ITEM(a), autoupdate());
    g_signal_connect(a, "toggled", G_CALLBACK(on_auto), NULL);
    g_signal_connect(c, "activate", G_CALLBACK(on_check), NULL);
    g_signal_connect(ab, "activate", G_CALLBACK(on_about), NULL);
    g_signal_connect(q, "activate", G_CALLBACK(on_quit), NULL);
    gtk_menu_shell_append(GTK_MENU_SHELL(m), a);
    gtk_menu_shell_append(GTK_MENU_SHELL(m), c);
    gtk_menu_shell_append(GTK_MENU_SHELL(m), ab);
    gtk_menu_shell_append(GTK_MENU_SHELL(m), gtk_separator_menu_item_new());
    gtk_menu_shell_append(GTK_MENU_SHELL(m), q);
    gtk_widget_show_all(m);
    gtk_container_add(GTK_CONTAINER(b), gtk_image_new_from_icon_name("open-menu-symbolic", GTK_ICON_SIZE_BUTTON));
    gtk_menu_button_set_popup(GTK_MENU_BUTTON(b), m);
    return b;
}
