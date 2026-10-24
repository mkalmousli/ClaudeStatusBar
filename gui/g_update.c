/* Fills a card from the current View. */
#include "g_gui.h"

void card_sync(Card *c, const Row *r);

static void markup(GtkWidget *l, char *t) { gtk_label_set_markup(GTK_LABEL(l), t); g_free(t); }

static void set_limit(GtkWidget *m, GtkWidget *l, int ok, double used, long reset, long span, long now) {
    char d[24], rest[80] = "";
    meter_set(m, ok, used, ok && reset ? (double)(span - (reset - now)) / (double)span : -1);
    if (!ok) { markup(l, g_strdup("<span alpha=\"60%\">no data yet</span>")); return; }
    if (reset) { dur(reset - now, d, sizeof d); snprintf(rest, sizeof rest, "  ·  resets in %s", d); }
    markup(l, g_markup_printf_escaped("<span foreground=\"%s\"><b>%.0f%%</b></span><span alpha=\"65%%\">%s</span>", pct_hex(used), used, rest));
}

static void status(Card *c, const View *v) {
    char w[96] = "";
    if (!v->h5ok && !v->wkok) {
        markup(c->status, g_strdup("<span alpha=\"60%\">Send a message in Claude Code with this profile and usage shows up here.</span>"));
        return;
    }
    if (v->waste > 0) snprintf(w, sizeof w, "  ·  ~%.0f%% of your week will go unused", v->waste);
    if (v->h5ok && v->gap >= 0)
        markup(c->status, g_markup_printf_escaped("<span foreground=\"%s\">%s</span><span alpha=\"65%%\">%s</span>", pct_hex(v->gap * 1.5), pace_name[v->pace], w));
    else markup(c->status, g_markup_printf_escaped("<span alpha=\"65%%\">%s</span>", *w ? w + 5 : ""));
}

void card_update(Card *c, int k) {
    const Row *r = &rows[k];
    const View *v = &r->v;
    long now = now_s();
    markup(c->title, g_markup_printf_escaped("<span size=\"large\"><b>%s</b></span>", r->i.mcl ? r->i.label : "Default"));
    markup(c->sub, g_markup_printf_escaped("<span alpha=\"65%%\">%s</span>", r->acct[0] ? r->acct : "not signed in"));
    set_limit(c->m5, c->l5, v->h5ok, v->h5, v->h5r, H5, now);
    set_limit(c->mw, c->lw, v->wkok, v->wk, v->wkr, WK, now);
    status(c, v);
    gtk_widget_set_visible(c->login, !r->acct[0]);
    card_sync(c, r);
}
