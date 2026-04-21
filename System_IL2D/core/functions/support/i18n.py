from .utils import load_json, GAME_DATA_DIR

I18N_FILE = f"{GAME_DATA_DIR}/i18n.json"


def _load_translations():
    try:
        data = load_json(I18N_FILE)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"zh": {}, "en": {}}


TRANSLATIONS = _load_translations()


def _normalize_lang(lang):
    if not lang:
        return "zh"
    token = str(lang).lower().replace("_", "-")
    if token in ("zh", "zh-tw", "zh-hant", "zh-hk", "zh-mo"):
        return "zh"
    if token in TRANSLATIONS:
        return token
    return "zh"


def tr(lang, key, **kwargs):
    table = TRANSLATIONS.get(_normalize_lang(lang), TRANSLATIONS.get("zh", {}))
    text = table.get(key)
    if text is None:
        text = TRANSLATIONS.get("en", {}).get(key, key)
    if kwargs:
        try:
            return str(text).format(**kwargs)
        except Exception:
            return str(text)
    return str(text)
