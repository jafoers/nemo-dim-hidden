#!/usr/bin/python3
"""
nemo-dim-hidden — dim hidden files in Nemo list / compact view

Nemo already dims hidden files in icon view (built-in).  This extension
brings the same behaviour to list and compact views by hooking into every
text cell renderer and setting it to the GTK "insensitive" state for rows
whose filename starts with '.'.

Tested on Nemo 6.2 / Linux Mint.  Requires the nemo-python package.

Installation
------------
Copy nemo-dim-hidden.py to ~/.local/share/nemo-python/extensions/ and
restart Nemo (nemo -q && nemo).

Implementation notes
--------------------
* set_cell_data_func is used instead of a draw-signal overlay.  The overlay
  approach silently fails in list view because the draw signal fires before
  the extension connects (the window is already painted by the time the
  GLib idle callback runs), and subsequent redraws may be clipped to regions
  that exclude the hidden-file rows.  cell_data_func runs for every cell on
  every render pass regardless of clip region.

* Nemo.InfoProvider is listed as a base class in addition to
  Nemo.NameAndDescProvider.  In nemo-python 6.x, a class that only
  implements NameAndDescProvider is imported but never instantiated;
  adding a real provider interface (InfoProvider with a trivial stub)
  triggers the instantiation.

* set_cell_data_func replaces Nemo's own attribute binding for the renderer,
  so the text value must be set explicitly inside the func.  Each column's
  sort-column-id equals the model column that Nemo binds to the 'text'
  attribute, so model.get_value(it, sort_col_id) reproduces the original
  displayed text.
"""

import gi
gi.require_version('GLib', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Nemo', '3.0')

from gi.repository import GLib, GObject, Gtk, Nemo


class HiddenFileDimmer(GObject.GObject,
                       Nemo.InfoProvider,
                       Nemo.NameAndDescProvider):

    def __init__(self):
        GObject.GObject.__init__(self)
        self._hooked    = set()   # id(GtkTreeView) values already processed
        self._fname_col = {}      # id(GtkTreeView) → model column for filename
        GLib.idle_add(self._attach_to_app)

    # ---- InfoProvider stub -----------------------------------------------
    # Required so nemo-python actually instantiates this class; the method
    # itself does nothing beyond satisfying the interface.
    def update_file_info(self, file, update_complete, handle):
        return Nemo.OperationResult.COMPLETE

    # ---- setup --------------------------------------------------------------
    def _attach_to_app(self):
        app = Gtk.Application.get_default()
        if app is None:
            return True                        # retry on next idle tick
        app.connect('window-added', lambda _a, w: self._scan(w))
        for win in app.get_windows():
            self._scan(win)
        return False

    def _scan(self, widget):
        if isinstance(widget, Gtk.TreeView):
            self._hook(widget)
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                self._scan(child)
            # catch panes / split views added after the initial scan
            widget.connect('add', lambda _c, ch: GLib.idle_add(self._scan, ch))

    # ---- column discovery ---------------------------------------------------
    def _find_filename_col(self, tv):
        """Return the model column index that holds the display filename.

        The Name column is identified as the first GtkTreeViewColumn that has
        both a GtkCellRendererPixbuf (the file icon) and a GtkCellRendererText
        (the label).  Its sort-column-id is the same model column that Nemo
        binds to the renderer's 'text' attribute.
        """
        for col in tv.get_columns():
            cells = col.get_cells()
            if (any(isinstance(c, Gtk.CellRendererPixbuf) for c in cells) and
                    any(isinstance(c, Gtk.CellRendererText)   for c in cells)):
                idx = col.get_sort_column_id()
                if idx >= 0:
                    return idx
        return -1

    # ---- hooking ------------------------------------------------------------
    def _hook(self, tv):
        wid = id(tv)
        if wid in self._hooked:
            return
        self._hooked.add(wid)
        tv.connect('destroy', lambda w: (
            self._hooked.discard(id(w)),
            self._fname_col.pop(id(w), None),
        ))

        fname_col = self._find_filename_col(tv)
        if fname_col < 0:
            return
        self._fname_col[wid] = fname_col

        for col in tv.get_columns():
            text_col = col.get_sort_column_id()
            if text_col < 0:
                continue
            for renderer in col.get_cells():
                if isinstance(renderer, Gtk.CellRendererText):
                    col.set_cell_data_func(
                        renderer,
                        self._cell_data,
                        (fname_col, text_col),
                    )

        # Flush the already-visible rows through the new data func.
        GLib.idle_add(tv.queue_draw)

    # ---- cell data ----------------------------------------------------------
    def _cell_data(self, col, renderer, model, it, data):
        fname_col, text_col = data
        try:
            # Don't interfere while the user is typing a new filename.
            if renderer.props.editing:
                return

            # Reproduce the text Nemo would have shown via its attribute binding.
            text = model.get_value(it, text_col)
            renderer.set_property('text', str(text) if text is not None else '')

            fname = model.get_value(it, fname_col)
            is_hidden = fname is not None and str(fname).startswith('.')
            renderer.set_property('sensitive', not is_hidden)
        except Exception:
            renderer.set_property('sensitive', True)

    # ---- metadata -----------------------------------------------------------
    def get_name_and_desc(self):
        return ["nemo-dim-hidden:::Dims hidden files in Nemo list/compact view"]
