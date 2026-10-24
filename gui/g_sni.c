/* StatusNotifier through libayatana-appindicator, loaded at run time: no link-time need. */
#include "g_gui.h"
#include <dlfcn.h>

static void *(*ai_new)(const char *, const char *, int);
static void (*ai_status)(void *, int), (*ai_menu)(void *, GtkMenu *), (*ai_theme)(void *, const char *);
static void (*ai_icon)(void *, const char *, const char *), (*ai_label)(void *, const char *, const char *);

static int ai_load(void) {
    void *h = dlopen("libayatana-appindicator3.so.1", RTLD_LAZY);
    if (!h) h = dlopen("libappindicator3.so.1", RTLD_LAZY);
    if (!h) return 0;
    *(void **)&ai_new = dlsym(h, "app_indicator_new");
    *(void **)&ai_status = dlsym(h, "app_indicator_set_status");
    *(void **)&ai_menu = dlsym(h, "app_indicator_set_menu");
    *(void **)&ai_theme = dlsym(h, "app_indicator_set_icon_theme_path");
    *(void **)&ai_icon = dlsym(h, "app_indicator_set_icon_full");
    *(void **)&ai_label = dlsym(h, "app_indicator_set_label");
    return ai_new && ai_status && ai_menu && ai_theme && ai_icon && ai_label;
}

/* Is a panel listening for StatusNotifier icons? */
int sni_watcher(void) {
    GDBusConnection *c = g_bus_get_sync(G_BUS_TYPE_SESSION, NULL, NULL);
    GVariant *r;
    gboolean has = FALSE;
    if (!c) return 0;
    r = g_dbus_connection_call_sync(c, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "NameHasOwner", g_variant_new("(s)", "org.kde.StatusNotifierWatcher"), G_VARIANT_TYPE("(b)"),
            G_DBUS_CALL_FLAGS_NONE, 500, NULL, NULL);
    if (r) { g_variant_get(r, "(b)", &has); g_variant_unref(r); }
    return has;
}

void *sni_open(const char *dir, const char *icon, GtkWidget *menu) {
    void *i;
    if (!sni_watcher() || !ai_load()) return NULL;
    i = ai_new("claudebar", icon, 0);
    ai_theme(i, dir);
    ai_status(i, 1);
    ai_menu(i, GTK_MENU(menu));
    return i;
}

void sni_set(void *i, const char *icon, const char *label) {
    ai_icon(i, icon, "claudebar");
    ai_label(i, label, "5h 100% · wk 100%");
}
