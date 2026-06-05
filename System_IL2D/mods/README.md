# IL2D Mods

Drop optional runtime mods in this folder as `.py` files.

Supported layouts:

- `mods/<name>.py`
- `mods/<folder>/*_main.py`

Optional entry wrappers such as `*_entry.py` may exist, but the loader now
prefers the actual `*_main.py` module inside each mod folder.

Each mod can expose either:

- `register_mod(ctx)`
- `register(ctx)`

If a mod throws an exception while loading, the core keeps running.
Load results are stored in runtime context:

- `ctx["loaded_mods"]`
- `ctx["mod_errors"]`
