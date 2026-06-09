import json
import os
import pygame


class AudioManager:
    def __init__(
        self,
        bgm_path=None,
        sfx_index_path=None,
        bgm_volume=0.4,
        sfx_volume=0.7,
    ):
        self.bgm_path = bgm_path
        self.sfx_index_path = sfx_index_path

        self.bgm_volume = self._clamp_volume(bgm_volume)
        self.sfx_volume = self._clamp_volume(sfx_volume)

        self.sfx_paths = {}
        self.sfx_cache = {}
        self.bgm_playing = False

        if not self.sfx_index_path:
            base_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..")
            )

            self.sfx_index_path = os.path.join(
                base_dir,
                "core",
                "Pre_coded_data",
                "game_data",
                "audio_sfx.json"
            )

        self.load_sfx_index(self.sfx_index_path)

    def _clamp_volume(self, volume):
        try:
            return max(0.0, min(1.0, float(volume)))
        except Exception:
            return 0.5

    def load_sfx_index(self, path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                print("[audio] sfx index must be an object")
                self.sfx_paths = {}
                return

            self.sfx_paths = data

        except Exception as exc:
            print(f"[audio] sfx index load failed: {exc}")
            self.sfx_paths = {}

    def play_bgm(self, bgm_path=None):
        if bgm_path:
            self.bgm_path = bgm_path

        if not self.bgm_path:
            print("[audio] no bgm path")
            return

        if not os.path.exists(self.bgm_path):
            print(f"[audio] bgm file not found: {self.bgm_path}")
            return

        try:
            pygame.mixer.music.load(self.bgm_path)
            pygame.mixer.music.set_volume(self.bgm_volume)
            pygame.mixer.music.play(-1)
            self.bgm_playing = True
        except Exception as exc:
            print(f"[audio] bgm play failed: {exc}")

    def stop_bgm(self):
        try:
            pygame.mixer.music.stop()
            self.bgm_playing = False
        except Exception as exc:
            print(f"[audio] bgm stop failed: {exc}")

    def pause_bgm(self):
        try:
            pygame.mixer.music.pause()
        except Exception as exc:
            print(f"[audio] bgm pause failed: {exc}")

    def resume_bgm(self):
        try:
            pygame.mixer.music.unpause()
        except Exception as exc:
            print(f"[audio] bgm resume failed: {exc}")

    def play_sfx(self, sfx_id):
        if not sfx_id:
            return

        path = self.sfx_paths.get(sfx_id)

        if not path:
            print(f"[audio] unknown sfx id: {sfx_id}")
            return

        if not os.path.exists(path):
            print(f"[audio] sfx file not found: {path}")
            return

        try:
            sound = self.sfx_cache.get(sfx_id)

            if sound is None:
                sound = pygame.mixer.Sound(path)
                sound.set_volume(self.sfx_volume)
                self.sfx_cache[sfx_id] = sound

            sound.play()

        except Exception as exc:
            print(f"[audio] sfx play failed {sfx_id}: {exc}")

    def set_bgm_volume(self, volume):
        self.bgm_volume = self._clamp_volume(volume)
        try:
            pygame.mixer.music.set_volume(self.bgm_volume)
        except Exception as exc:
            print(f"[audio] set bgm volume failed: {exc}")

    def set_sfx_volume(self, volume):
        self.sfx_volume = self._clamp_volume(volume)

        for sound in self.sfx_cache.values():
            try:
                sound.set_volume(self.sfx_volume)
            except Exception:
                pass

    def clear_sfx_cache(self):
        self.sfx_cache.clear()
    def play_sfx_safe(game, sfx_id):
        audio = getattr(game, "audio", None)
        if not audio:
            return
        try:
            audio.play_sfx(sfx_id)
        except Exception as exc:
            print(f"[audio] play_sfx_safe failed {sfx_id}: {exc}")