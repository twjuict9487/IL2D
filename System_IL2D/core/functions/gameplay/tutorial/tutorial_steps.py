def build_tutorial_steps(_lang="zh"):
    # All player-facing text is resolved through i18n keys in tutorial_core.
    return [
        {
            "id": "move_basic",
            "title_key": "tutorial.dev.step.1.title",
            "hint_key": "tutorial.dev.step.1.hint",
        },
        {
            "id": "combat_intro",
            "title_key": "tutorial.dev.step.2.title",
            "hint_key": "tutorial.dev.step.2.hint",
        },
        {
            "id": "kill_wave_1",
            "title_key": "tutorial.dev.step.3.title",
            "hint_key": "tutorial.dev.step.3.hint",
        },
        {
            "id": "npc_intro",
            "title_key": "tutorial.dev.step.4.title",
            "hint_key": "tutorial.dev.step.4.hint",
        },
        {
            "id": "esc_open",
            "title_key": "tutorial.dev.step.5.title",
            "hint_key": "tutorial.dev.step.5.hint",
        },
        {
            "id": "esc_close",
            "title_key": "tutorial.dev.step.6.title",
            "hint_key": "tutorial.dev.step.6.hint",
        },
        {
            "id": "finish_reset",
            "title_key": "tutorial.dev.step.7.title",
            "hint_key": "tutorial.dev.step.7.hint",
        },
    ]
