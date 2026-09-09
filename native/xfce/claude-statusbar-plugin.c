/* claude-statusbar — a native xfce4-panel plugin.
 *
 * xfce4-panel 4.x dlopens each plugin and calls xfce_panel_module_construct(),
 * so a panel item has to be a C shared library; the X-XFCE-Exec protocol that
 * allowed an arbitrary executable was removed after Xfce 4.4.
 *
 * The module is deliberately thin.  All of the logic — reading Claude's state,
 * choosing which session's reading is current, drawing the meters, and the
 * settings — lives in the Python package, which this plugin asks for four
 * fields: the SVG, the refresh interval, the file to watch, and the tooltip.
 * Nothing here is configurable, so a setting change needs no rebuild.
 *
 * Updates are event-driven: a file monitor on the state file redraws as soon
 * as a Claude session writes, and the interval is only a fallback for the
 * clock-driven parts (countdowns, "updated 3m ago").
 */

#include <gtk/gtk.h>
#include <libxfce4panel/libxfce4panel.h>
#include <string.h>

/* Coalesce the burst of events one atomic save produces (write + rename). */
#define SETTLE_MILLISECONDS 120
#define FALLBACK_INTERVAL_MS 20000

typedef struct
{
  XfcePanelPlugin *plugin;
  GtkWidget       *ebox;
  GtkWidget       *image;
  gchar           *program;       /* absolute path to claude-statusbar */
  guint            timeout_id;    /* periodic fallback refresh */
  guint            settle_id;     /* debounce for file-monitor events */
  guint            interval_ms;   /* what the Python side last told us */
  gint             size;          /* one panel row, in pixels */
  GFileMonitor    *monitor;
  gchar           *watched;       /* state file we are monitoring */
  gboolean         busy;          /* a refresh is already in flight */
} ClaudePlugin;

static void refresh (ClaudePlugin *claude);

/* The height of a single row.  xfce_panel_plugin_get_size() reports the whole
   panel, which on a multi-row panel is a multiple of what one item gets. */
static gint
row_size (XfcePanelPlugin *plugin)
{
  gint rows = xfce_panel_plugin_get_nrows (plugin);
  gint size = xfce_panel_plugin_get_size (plugin);

  return (rows > 1) ? size / rows : size;
}

/* Find the launcher: PATH first, then the usual per-user install. */
static gchar *
find_program (void)
{
  gchar *found = g_find_program_in_path ("claude-statusbar");
  if (found != NULL)
    return found;

  gchar *local = g_build_filename (g_get_home_dir (), ".local", "bin",
                                   "claude-statusbar", NULL);
  if (g_file_test (local, G_FILE_TEST_IS_EXECUTABLE))
    return local;

  g_free (local);
  return NULL;
}

static void
show_message (ClaudePlugin *claude, const gchar *text)
{
  GtkWidget *child = gtk_bin_get_child (GTK_BIN (claude->ebox));

  if (GTK_IS_LABEL (child))
    {
      gtk_label_set_text (GTK_LABEL (child), text);
      return;
    }
  if (child != NULL)
    gtk_widget_destroy (child);
  claude->image = gtk_label_new (text);
  gtk_container_add (GTK_CONTAINER (claude->ebox), claude->image);
  gtk_widget_show_all (claude->ebox);
}

static gboolean
on_timeout (gpointer data)
{
  refresh (data);
  return G_SOURCE_CONTINUE;
}

/* Re-arm the periodic refresh only when the interval actually changed, so a
   steady interval does not reset its phase on every cycle. */
static void
apply_interval (ClaudePlugin *claude, guint interval_ms)
{
  if (interval_ms < 200)
    interval_ms = 200;
  if (interval_ms == claude->interval_ms && claude->timeout_id != 0)
    return;

  claude->interval_ms = interval_ms;
  if (claude->timeout_id != 0)
    g_source_remove (claude->timeout_id);
  claude->timeout_id = g_timeout_add (interval_ms, on_timeout, claude);
}

static gboolean
on_settled (gpointer data)
{
  ClaudePlugin *claude = data;

  claude->settle_id = 0;
  refresh (claude);
  return G_SOURCE_REMOVE;
}

static void
on_state_changed (GFileMonitor *monitor, GFile *file, GFile *other,
                  GFileMonitorEvent event, gpointer data)
{
  ClaudePlugin *claude = data;
  gchar *name = g_file_get_basename (file);
  gboolean ours = (claude->watched != NULL && name != NULL
                   && g_str_has_suffix (claude->watched, name));

  g_free (name);
  if (!ours)
    return;

  /* One save fires several events; wait for quiet, then redraw once. */
  if (claude->settle_id != 0)
    g_source_remove (claude->settle_id);
  claude->settle_id = g_timeout_add (SETTLE_MILLISECONDS, on_settled, claude);
}

/* Watch the directory rather than the file: the state is saved by writing a
   temporary file and renaming it over the target, which replaces the inode a
   file monitor would otherwise still be holding. */
static void
watch_state_file (ClaudePlugin *claude, const gchar *path)
{
  if (path == NULL || *path == '\0')
    return;
  if (claude->watched != NULL && g_strcmp0 (claude->watched, path) == 0)
    return;

  g_free (claude->watched);
  claude->watched = g_strdup (path);

  if (claude->monitor != NULL)
    {
      g_object_unref (claude->monitor);
      claude->monitor = NULL;
    }

  gchar *dirname = g_path_get_dirname (path);
  GFile *dir = g_file_new_for_path (dirname);
  claude->monitor = g_file_monitor_directory (dir, G_FILE_MONITOR_WATCH_MOVES,
                                              NULL, NULL);
  if (claude->monitor != NULL)
    g_signal_connect (claude->monitor, "changed",
                      G_CALLBACK (on_state_changed), claude);

  g_object_unref (dir);
  g_free (dirname);
}

/* Render the SVG the Python side produced and hang the tooltip off it. */
static void
apply_output (ClaudePlugin *claude, const gchar *output)
{
  gchar **parts = g_strsplit (output, "\n", 4);
  guint count = g_strv_length (parts);

  if (count < 1 || parts[0][0] == '\0')
    {
      g_strfreev (parts);
      return;
    }

  GdkPixbufLoader *loader = gdk_pixbuf_loader_new_with_type ("svg", NULL);
  GdkPixbuf *pixbuf = NULL;

  if (loader != NULL
      && gdk_pixbuf_loader_write (loader, (const guchar *) parts[0],
                                  strlen (parts[0]), NULL)
      && gdk_pixbuf_loader_close (loader, NULL))
    pixbuf = gdk_pixbuf_loader_get_pixbuf (loader);

  if (pixbuf != NULL)
    {
      if (!GTK_IS_IMAGE (claude->image))
        {
          GtkWidget *child = gtk_bin_get_child (GTK_BIN (claude->ebox));
          if (child != NULL)
            gtk_widget_destroy (child);
          claude->image = gtk_image_new ();
          gtk_container_add (GTK_CONTAINER (claude->ebox), claude->image);
          gtk_widget_show_all (claude->ebox);
        }
      gtk_image_set_from_pixbuf (GTK_IMAGE (claude->image), pixbuf);
    }
  else
    {
      /* No SVG pixbuf loader on this box (librsvg2-common missing). */
      show_message (claude, "claude: no SVG loader");
    }

  if (count > 1)
    apply_interval (claude, (guint) g_ascii_strtoull (parts[1], NULL, 10));
  if (count > 2)
    watch_state_file (claude, parts[2]);
  if (count > 3)
    gtk_widget_set_tooltip_text (claude->ebox, g_strchomp (parts[3]));

  if (loader != NULL)
    g_object_unref (loader);
  g_strfreev (parts);
}

static void
on_finished (GObject *source, GAsyncResult *result, gpointer data)
{
  ClaudePlugin *claude = data;
  gchar *output = NULL;
  GError *error = NULL;

  claude->busy = FALSE;
  if (g_subprocess_communicate_utf8_finish (G_SUBPROCESS (source), result,
                                            &output, NULL, &error))
    {
      if (output != NULL)
        apply_output (claude, output);
      g_free (output);
    }
  else
    {
      show_message (claude, "claude: ?");
      g_clear_error (&error);
    }
  g_object_unref (source);
}

/* Ask the Python package for the current picture, without blocking the panel. */
static void
refresh (ClaudePlugin *claude)
{
  if (claude->program == NULL)
    {
      show_message (claude, "claude-statusbar not found");
      return;
    }
  /* At a one-second interval a slow start could otherwise pile up. */
  if (claude->busy)
    return;

  gchar *height = g_strdup_printf ("%d", MAX (8, claude->size - 2));
  GError *error = NULL;
  GSubprocess *proc = g_subprocess_new (G_SUBPROCESS_FLAGS_STDOUT_PIPE
                                        | G_SUBPROCESS_FLAGS_STDERR_SILENCE,
                                        &error, claude->program, "--panel",
                                        height, NULL);
  g_free (height);

  if (proc == NULL)
    {
      show_message (claude, "claude: spawn failed");
      g_clear_error (&error);
      return;
    }
  claude->busy = TRUE;
  g_subprocess_communicate_utf8_async (proc, NULL, NULL, on_finished, claude);
}

static gboolean
on_clicked (GtkWidget *widget, GdkEventButton *event, gpointer data)
{
  ClaudePlugin *claude = data;

  if (event->button != 1 || claude->program == NULL)
    return FALSE;

  gchar *argv[] = { claude->program, "--gui", NULL };
  g_spawn_async (NULL, argv, NULL, G_SPAWN_DEFAULT, NULL, NULL, NULL, NULL);
  return TRUE;
}

static gboolean
on_size_changed (XfcePanelPlugin *plugin, gint size, gpointer data)
{
  ClaudePlugin *claude = data;
  gint rows = xfce_panel_plugin_get_nrows (plugin);
  gint wanted = (rows > 1) ? size / rows : size;

  /* The panel emits this while settling; only redraw on a real change. */
  if (wanted == claude->size)
    return TRUE;

  claude->size = wanted;
  refresh (claude);
  return TRUE;
}

/* First paint, deferred to the main loop.
 *
 * At construct time the panel has not finished applying the plugin's
 * properties, so xfce_panel_plugin_get_size() still reports a default and the
 * meters came out too small.  By the time an idle callback runs, the real
 * size is in place. */
static gboolean
on_first_paint (gpointer data)
{
  ClaudePlugin *claude = data;

  claude->size = row_size (claude->plugin);
  refresh (claude);
  return G_SOURCE_REMOVE;
}

static void
on_free (XfcePanelPlugin *plugin, gpointer data)
{
  ClaudePlugin *claude = data;

  if (claude->timeout_id != 0)
    g_source_remove (claude->timeout_id);
  if (claude->settle_id != 0)
    g_source_remove (claude->settle_id);
  if (claude->monitor != NULL)
    g_object_unref (claude->monitor);
  g_free (claude->watched);
  g_free (claude->program);
  g_slice_free (ClaudePlugin, claude);
}

static void
claude_statusbar_construct (XfcePanelPlugin *plugin)
{
  ClaudePlugin *claude = g_slice_new0 (ClaudePlugin);

  claude->plugin = plugin;
  claude->program = find_program ();
  claude->size = row_size (plugin);

  claude->ebox = gtk_event_box_new ();
  gtk_event_box_set_visible_window (GTK_EVENT_BOX (claude->ebox), FALSE);
  claude->image = gtk_image_new ();
  gtk_container_add (GTK_CONTAINER (claude->ebox), claude->image);
  gtk_container_add (GTK_CONTAINER (plugin), claude->ebox);
  gtk_widget_show_all (claude->ebox);

  xfce_panel_plugin_add_action_widget (plugin, claude->ebox);
  g_signal_connect (claude->ebox, "button-press-event",
                    G_CALLBACK (on_clicked), claude);
  g_signal_connect (plugin, "size-changed", G_CALLBACK (on_size_changed), claude);
  g_signal_connect (plugin, "free-data", G_CALLBACK (on_free), claude);

  /* The first refresh reports the real interval and the file to watch, and
     runs once the panel has given the plugin its true size. */
  apply_interval (claude, FALLBACK_INTERVAL_MS);
  g_idle_add (on_first_paint, claude);
}

XFCE_PANEL_PLUGIN_REGISTER (claude_statusbar_construct);
