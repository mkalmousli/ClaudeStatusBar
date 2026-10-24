/* claudebar-gui: window plus tray icon. A second launch just shows the window. */
#include "g_gui.h"
#include <unistd.h>

static int hidden, started;

static gboolean tick(gpointer d) {
    static long last;
    long now = now_s();
    (void)d;
    if (now - last >= 30) {
        last = now;
        auto_capture();
        for (int k = 0; k < nrows; k++) perfect_tick(&rows[k].i);
    }
    rows_reload();
    win_update();
    tray_update();
    return TRUE;
}

/* Autostart starts hidden; with no tray to come back from, show the window after all. */
static gboolean fallback(gpointer d) {
    (void)d;
    if (!tray_ok()) win_show(0);
    return FALSE;
}

static void activate(GApplication *a, gpointer d) {
    (void)d;
    if (!started) {
        started = 1;
        g_application_hold(a);
        win_init(GTK_APPLICATION(a));
        tray_init();
        tick(NULL);
        g_timeout_add_seconds(1, tick, NULL);
        if (hidden) g_timeout_add_seconds(3, fallback, NULL);
        else win_show(0);
    } else win_show(0);
}

int main(int argc, char **argv) {
    char *args[] = {argv[0], NULL};
    GtkApplication *app;
    int rc;
    if (argc > 1 && !strcmp(argv[1], "--version")) { puts(VERSION); return 0; }
    hidden = argc > 1 && !strcmp(argv[1], "--hidden");
    app = gtk_application_new("io.github.mkalmousli.claudebar", G_APPLICATION_FLAGS_NONE);
    g_signal_connect(app, "activate", G_CALLBACK(activate), NULL);
    rc = g_application_run(G_APPLICATION(app), 1, args);
    g_object_unref(app);
    return rc;
}
