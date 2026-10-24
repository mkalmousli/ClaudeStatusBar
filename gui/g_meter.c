/* A usage bar: the fill is how much you used, the line is how much of the window is gone. */
#include "g_gui.h"
#include <math.h>

typedef struct { int ok; double used, el; } M;
static const double RGB[][3] = {{12, 163, 12}, {250, 178, 25}, {236, 131, 90}, {242, 85, 90}};
static const char *HEX[] = {"#0ca30c", "#c98a00", "#d9632b", "#f2555a"};

static int band(double pct) { return pct < 50 ? 0 : pct < 75 ? 1 : pct < 90 ? 2 : 3; }
const char *pct_hex(double pct) { return HEX[band(pct)]; }
void rgb_set(cairo_t *c, double pct) {
    const double *k = RGB[band(pct)];
    cairo_set_source_rgb(c, k[0] / 255, k[1] / 255, k[2] / 255);
}

static void track(cairo_t *c, double w, double h) {
    double r = h / 2;
    cairo_new_sub_path(c);
    cairo_arc(c, w - r, r, r, -M_PI / 2, M_PI / 2);
    cairo_arc(c, r, r, r, M_PI / 2, 3 * M_PI / 2);
    cairo_close_path(c);
}

static gboolean paint(GtkWidget *w, cairo_t *c, gpointer d) {
    M *m = d;
    double W = gtk_widget_get_allocated_width(w), H = gtk_widget_get_allocated_height(w);
    GdkRGBA fg;
    gtk_style_context_get_color(gtk_widget_get_style_context(w), GTK_STATE_FLAG_NORMAL, &fg);
    track(c, W, H);
    cairo_clip(c);
    gdk_cairo_set_source_rgba(c, &fg);
    cairo_paint_with_alpha(c, 0.15);
    if (m->ok) {
        rgb_set(c, m->used);
        cairo_rectangle(c, 0, 0, W * fmin(m->used, 100) / 100, H);
        cairo_fill(c);
    }
    if (m->ok && m->el >= 0) {
        gdk_cairo_set_source_rgba(c, &fg);
        cairo_rectangle(c, W * fmin(m->el, 1) - 1, 0, 2, H);
        cairo_fill(c);
    }
    return FALSE;
}

GtkWidget *meter_new(void) {
    GtkWidget *w = gtk_drawing_area_new();
    M *m = g_new0(M, 1);
    gtk_widget_set_size_request(w, 120, 14);
    gtk_widget_set_hexpand(w, TRUE);
    gtk_widget_set_valign(w, GTK_ALIGN_CENTER);
    g_object_set_data_full(G_OBJECT(w), "m", m, g_free);
    g_signal_connect(w, "draw", G_CALLBACK(paint), m);
    return w;
}

void meter_set(GtkWidget *w, int ok, double used, double el) {
    M *m = g_object_get_data(G_OBJECT(w), "m");
    m->ok = ok, m->used = used, m->el = el;
    gtk_widget_queue_draw(w);
}
