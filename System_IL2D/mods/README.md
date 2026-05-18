# IL2D Mods

Drop optional runtime mods in this folder as `.py` files.

Each mod can expose either:

- `register_mod(ctx)`
- `register(ctx)`

If a mod throws an exception while loading, the core keeps running.
Load results are stored in runtime context:

- `ctx["loaded_mods"]`
- `ctx["mod_errors"]`
