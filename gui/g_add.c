/* Adding and removing profiles. A new profile goes straight to sign-in. */
#include "g_gui.h"

void note_box(GtkWindow *w, const char *text) {
    GtkWidget *d = gtk_message_dialog_new(w, GTK_DIALOG_MODAL, GTK_MESSAGE_INFO, GTK_BUTTONS_OK, "%s", text);
    gtk_dialog_run(GTK_DIALOG(d));
    gtk_widget_destroy(d);
}

static void signin(GtkWindow *w, const char *name) {
    if (!term_run(name)) note_box(w, "Profile added. Sign in by running:\n\nclaudebar run <profile>");
}

void add_dialog(GtkWindow *w) {
    GtkWidget *d = gtk_dialog_new_with_buttons("Add profile", w, GTK_DIALOG_MODAL, "Cancel", GTK_RESPONSE_CANCEL,
                                               "Add", GTK_RESPONSE_OK, NULL);
    GtkWidget *box = gtk_dialog_get_content_area(GTK_DIALOG(d)), *e = gtk_entry_new(), *err = gtk_label_new("");
    GtkWidget *share = gtk_check_button_new_with_label("Share settings, commands and skills with Default");
    gtk_container_set_border_width(GTK_CONTAINER(box), 14);
    gtk_box_set_spacing(GTK_BOX(box), 10);
    gtk_entry_set_placeholder_text(GTK_ENTRY(e), "Name, for example work");
    gtk_entry_set_activates_default(GTK_ENTRY(e), TRUE);
    gtk_dialog_set_default_response(GTK_DIALOG(d), GTK_RESPONSE_OK);
    gtk_box_pack_start(GTK_BOX(box), gtk_label_new("A profile is a separate Claude login with its own usage."), FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), e, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), share, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), err, FALSE, FALSE, 0);
    gtk_widget_show_all(d);
    while (gtk_dialog_run(GTK_DIALOG(d)) == GTK_RESPONSE_OK) {
        const char *name = gtk_entry_get_text(GTK_ENTRY(e)),
                   *bad = profile_add(name, gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(share)));
        if (!bad) { rows_reload(); win_update(); signin(w, name); break; }
        gtk_label_set_markup(GTK_LABEL(err), g_markup_printf_escaped("<span foreground=\"#d33\">%s</span>", bad));
    }
    gtk_widget_destroy(d);
}

void remove_dialog(GtkWindow *w, int k) {
    GtkWidget *d;
    const char *bad;
    if (k >= nrows) return;
    d = gtk_message_dialog_new(w, GTK_DIALOG_MODAL, GTK_MESSAGE_WARNING, GTK_BUTTONS_NONE, "Remove “%s”?", rows[k].i.label);
    gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(d), "This signs the profile out and deletes its settings and history.");
    gtk_dialog_add_buttons(GTK_DIALOG(d), "Cancel", GTK_RESPONSE_CANCEL, "Remove", GTK_RESPONSE_OK, NULL);
    gtk_dialog_set_default_response(GTK_DIALOG(d), GTK_RESPONSE_CANCEL);
    if (gtk_dialog_run(GTK_DIALOG(d)) == GTK_RESPONSE_OK && (bad = profile_remove(&rows[k].i))) note_box(w, bad);
    gtk_widget_destroy(d);
}
