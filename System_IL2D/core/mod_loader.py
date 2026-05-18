import importlib.util
import os
import traceback


def _iter_mod_files(mods_dir):
    if not os.path.isdir(mods_dir):
        return []
    files = []
    for name in sorted(os.listdir(mods_dir)):
        if not name.endswith(".py"):
            continue
        if name.startswith("_"):
            continue
        path = os.path.join(mods_dir, name)
        if os.path.isfile(path):
            files.append(path)
    return files


def _load_module_from_path(path):
    mod_name = f"il2d_mod_{os.path.splitext(os.path.basename(path))[0]}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to build import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_mods(ctx, mods_dir):
    if "mod_hooks" not in ctx or not isinstance(ctx.get("mod_hooks"), dict):
        ctx["mod_hooks"] = {}
    loaded = []
    errors = []

    for path in _iter_mod_files(mods_dir):
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            module = _load_module_from_path(path)
            register = getattr(module, "register_mod", None)
            if register is None:
                register = getattr(module, "register", None)
            if callable(register):
                register(ctx)
            loaded.append(name)
        except Exception as exc:
            errors.append(
                {
                    "mod": name,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    ctx["loaded_mods"] = loaded
    ctx["mod_errors"] = errors
    return loaded, errors


def register_hook(ctx, hook_name, fn):
    hooks = ctx.setdefault("mod_hooks", {})
    hooks.setdefault(hook_name, []).append(fn)


def invoke_hooks(ctx, hook_name, *args, stop_on_true=False, **kwargs):
    hooks = ctx.get("mod_hooks", {})
    fns = hooks.get(hook_name, [])
    result = False
    for fn in fns:
        try:
            ret = fn(ctx, *args, **kwargs)
            if stop_on_true and ret:
                return True
            result = result or bool(ret)
        except Exception as exc:
            ctx.setdefault("mod_errors", []).append(
                {
                    "mod": getattr(fn, "__module__", "unknown"),
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )
    return result
