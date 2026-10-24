/* The tray icon: a ring filled to your 5h usage, with the number inside. A PNG,
 * because every tray protocol (StatusNotifier, XEmbed) can show a file. */
#include "g_gui.h"
#include <math.h>

void icon_png(const char *path, int ok, double pct) {
    cairo_surface_t *s = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, 48, 48);
    cairo_t *c = cairo_create(s);
    cairo_text_extents_t e;
    char t[8];
    cairo_set_source_rgba(c, 0.1, 0.1, 0.13, 0.92);
    cairo_arc(c, 24, 24, 23, 0, 2 * M_PI);
    cairo_fill(c);
    cairo_set_line_width(c, 6);
    cairo_set_source_rgba(c, 0.6, 0.6, 0.6, 0.45);
    cairo_arc(c, 24, 24, 19, 0, 2 * M_PI);
    cairo_stroke(c);
    if (ok) {
        rgb_set(c, pct);
        cairo_arc(c, 24, 24, 19, -M_PI / 2, -M_PI / 2 + 2 * M_PI * fmin(pct, 100) / 100);
        cairo_stroke(c);
    }
    snprintf(t, sizeof t, ok ? "%.0f" : "-", pct);
    cairo_select_font_face(c, "sans", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_BOLD);
    cairo_set_font_size(c, strlen(t) > 2 ? 15 : 20);
    cairo_text_extents(c, t, &e);
    cairo_set_source_rgb(c, 1, 1, 1);
    cairo_move_to(c, 24 - (e.width / 2 + e.x_bearing), 24 - (e.height / 2 + e.y_bearing));
    cairo_show_text(c, t);
    cairo_surface_write_to_png(s, path);
    cairo_destroy(c);
    cairo_surface_destroy(s);
}
