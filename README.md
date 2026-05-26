# nemo-dim-hidden

A [nemo-python](https://github.com/linuxmint/nemo-python) extension that dims
hidden files (dotfiles) in Nemo's **list view**.

Nemo already dims hidden files in icon view out of the box. This extension
brings the same visual treatment to list view, greying out the Name, Size,
Type, Date Modified columns (and any other text columns you have enabled)
for every file whose name starts with `.`.

> **Compact view**: Nemo natively dims the file icon in compact view (50 %
> opacity). The text labels there are rendered on an EelCanvas with no Python
> API, so this extension cannot affect them.

## Requirements

- Nemo ≥ 3.0 (tested on 6.2 / Linux Mint 22)
- `nemo-python` package

```
sudo apt install nemo-python   # Debian / Ubuntu / Mint
```

## Installation

```bash
mkdir -p ~/.local/share/nemo-python/extensions/
cp nemo-dim-hidden.py ~/.local/share/nemo-python/extensions/
nemo -q && nemo
```

To uninstall, delete the file and restart Nemo.

## How it works

GTK's `GtkCellRenderer` has a `sensitive` property: when `False`, the theme
renders the cell in its "insensitive" (greyed-out) state.  The extension hooks
into every text cell renderer in the file-list tree view via
`set_cell_data_func`, checks whether the filename starts with `.`, and sets
`sensitive` accordingly on every render pass.

A few non-obvious things worth knowing if you're reading the source:

- **`InfoProvider` stub** — in nemo-python 6.x, a class that only implements
  `NameAndDescProvider` is imported but never instantiated. Adding `InfoProvider`
  (with a trivial do-nothing stub) is necessary to get the class instantiated.

- **`set_cell_data_func` replaces attribute bindings** — Nemo normally binds
  model columns to renderer properties via `add_attribute`. Calling
  `set_cell_data_func` overrides this, so the text value must be set explicitly
  inside the callback.  Each column's `sort-column-id` equals the model column
  Nemo uses for the `text` attribute, so
  `model.get_value(it, col.get_sort_column_id())` reproduces the original text.

- **draw-signal overlay doesn't work** — the draw signal fires before the
  extension's idle callback connects to it (the window is already painted), and
  later redraws may be clipped to regions that exclude hidden-file rows.
  `set_cell_data_func` runs for every cell on every render pass, bypassing
  both issues.

## License

MIT
