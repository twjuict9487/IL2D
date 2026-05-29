def build_tutorial_steps(_lang="zh"):
    # All player-facing text is resolved through i18n keys in tutorial_core.
    return [
        {"id": "move_basic", "title_key": "tutorial.dev.step.1.title", "hint_key": "tutorial.dev.step.1.hint"},
        {"id": "combat_intro", "title_key": "tutorial.dev.step.2.title", "hint_key": "tutorial.dev.step.2.hint"},
        {"id": "kill_wave_1", "title_key": "tutorial.dev.step.3.title", "hint_key": "tutorial.dev.step.3.hint"},
        {"id": "npc_shop", "title_key": "tutorial.dev.step.4.title", "hint_key": "tutorial.dev.step.4.hint"},
        {"id": "esc_open", "title_key": "tutorial.dev.step.5.title", "hint_key": "tutorial.dev.step.5.hint"},
        {"id": "hotbar_item", "title_key": "tutorial.dev.step.6.title", "hint_key": "tutorial.dev.step.6.hint"},
        {"id": "hotbar_magic", "title_key": "tutorial.dev.step.7.title", "hint_key": "tutorial.dev.step.7.hint"},
        {"id": "equip_bought", "title_key": "tutorial.dev.step.8.title", "hint_key": "tutorial.dev.step.8.hint"},
        {"id": "save_once", "title_key": "tutorial.dev.step.9.title", "hint_key": "tutorial.dev.step.9.hint"},
        {"id": "esc_close", "title_key": "tutorial.dev.step.10.title", "hint_key": "tutorial.dev.step.10.hint"},
        {"id": "kill_wave_2", "title_key": "tutorial.dev.step.11.title", "hint_key": "tutorial.dev.step.11.hint"},
        {"id": "objective_intro", "title_key": "tutorial.dev.step.12.title", "hint_key": "tutorial.dev.step.12.hint"},
        {"id": "rogue_intro", "title_key": "tutorial.dev.step.13.title", "hint_key": "tutorial.dev.step.13.hint"},
        {"id": "finish_reset", "title_key": "tutorial.dev.step.14.title", "hint_key": "tutorial.dev.step.14.hint"},
    ]
