import importlib.util as iu, os, traceback


def _iter_mod_files(d):
    if not os.path.isdir(d):
        return []
    out = []
    for r, ds, fs in os.walk(d):
        ds[:] = sorted(x for x in ds if x != "__pycache__" and not x.startswith("."))
        for f in sorted(fs):
            p = os.path.join(r, f)
            rel = os.path.relpath(p, d)
            if (
                f.endswith(".py")
                and not f.startswith("_")
                and f != "__init__.py"
                and not f.endswith("_entry.py")
                and os.path.isfile(p)
                and (not os.path.dirname(rel) or f.endswith("_main.py"))
            ):
                out.append(p)
    return out


def _load_module_from_path(p, d):
    rel = (
        os.path.splitext(os.path.relpath(p, d))[0]
        .replace(os.sep, ".")
        .replace("\\", ".")
        .replace("/", ".")
    )
    spec = iu.spec_from_file_location(f"mods.{rel}", p)
    if not spec or not spec.loader:
        raise RuntimeError("failed to build import spec")
    m = iu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_mods(ctx, mods_dir):
    if not isinstance(ctx.get("mod_hooks"), dict):
        ctx["mod_hooks"] = {}
    loaded, errors = [], []
    for p in _iter_mod_files(mods_dir):
        name = os.path.relpath(p, mods_dir)
        try:
            m = _load_module_from_path(p, mods_dir)
            reg = getattr(m, "register_mod", None) or getattr(m, "register", None)
            if callable(reg):
                reg(ctx)
            loaded.append(name)
        except Exception as e:
            errors.append(
                {"mod": name, "error": str(e), "traceback": traceback.format_exc()}
            )
    ctx["loaded_mods"], ctx["mod_errors"] = loaded, errors
    return loaded, errors


def register_hook(ctx, hook_name, fn):
    ctx.setdefault("mod_hooks", {}).setdefault(hook_name, []).append(fn)


def invoke_hooks(ctx, hook_name, *args, stop_on_true=False, **kwargs):
    res = False
    for fn in ctx.get("mod_hooks", {}).get(hook_name, []):
        try:
            ret = fn(ctx, *args, **kwargs)
            if stop_on_true and ret:
                return True
            res |= bool(ret)
        except Exception as e:
            ctx.setdefault("mod_errors", []).append(
                {
                    "mod": getattr(fn, "__module__", "unknown"),
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
    return res
