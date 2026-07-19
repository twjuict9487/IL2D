import json
import os
import pygame
from ..support.asset_resolver import ensure_primed_from_file, resolve_audio_candidates
from ..support.utils import GAME_DATA_DIR

DEFAULT_BGM_ID = "短兵相接"


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
        self.current_bgm_ref = None
        self.current_bgm_resolved = None
        self.bgm_segment_start = 0.0
        self.bgm_segment_end = None
        self.bgm_segment_loop = False
        ensure_primed_from_file(__file__)

        if not self.sfx_index_path:
            self.sfx_index_path = (
                os.path.join(GAME_DATA_DIR, "audio_sfx.json") if GAME_DATA_DIR else ""
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

    def _resolve_audio_path(self, audio_ref):
        if not audio_ref:
            return None
        raw = str(audio_ref).strip()
        if not raw:
            return None
        if os.path.isfile(raw):
            return raw
        for path in resolve_audio_candidates(raw):
            if path and os.path.isfile(path):
                return path
        return None

    def play_bgm(self, bgm_path=None, fade_ms=0, restart=False):
        if bgm_path:
            self.bgm_path = bgm_path

        if not self.bgm_path:
            self.bgm_path = DEFAULT_BGM_ID
        resolved = self._resolve_audio_path(self.bgm_path)
        if not resolved:
            print(f"[audio] bgm file not found: {self.bgm_path}")
            return False
        if (
            not restart
            and self.bgm_playing
            and self.current_bgm_resolved
            and self.current_bgm_resolved == resolved
        ):
            return True

        try:
            pygame.mixer.music.load(resolved)
            pygame.mixer.music.set_volume(self.bgm_volume)
            pygame.mixer.music.play(-1, fade_ms=max(0, int(fade_ms or 0)))
            self.bgm_playing = True
            self.current_bgm_ref = self.bgm_path
            self.current_bgm_resolved = resolved
            self.bgm_segment_start = 0.0
            self.bgm_segment_end = None
            self.bgm_segment_loop = False
            return True
        except Exception as exc:
            print(f"[audio] bgm play failed: {exc}")
            return False

    def play_bgm_segment(self, bgm_path, start=0.0, end=None, loop=False, fade_ms=0):
        resolved = self._resolve_audio_path(bgm_path)
        if not resolved:
            print(f"[audio] bgm file not found: {bgm_path}")
            return False
        try:
            start = max(0.0, float(start or 0.0))
            end = float(end) if end is not None else None
            if end is not None and end <= start:
                raise ValueError("segment end must be after start")
            pygame.mixer.music.load(resolved)
            pygame.mixer.music.set_volume(self.bgm_volume)
            pygame.mixer.music.play(
                0,
                start=start,
                fade_ms=max(0, int(fade_ms or 0)),
            )
            self.bgm_path = bgm_path
            self.bgm_playing = True
            self.current_bgm_ref = bgm_path
            self.current_bgm_resolved = resolved
            self.bgm_segment_start = start
            self.bgm_segment_end = end
            self.bgm_segment_loop = bool(loop)
            return True
        except Exception as exc:
            print(f"[audio] bgm segment play failed: {exc}")
            return False

    def get_bgm_position(self):
        if not self.bgm_playing:
            return None
        try:
            elapsed_ms = pygame.mixer.music.get_pos()
            if elapsed_ms < 0:
                return None
            return self.bgm_segment_start + elapsed_ms / 1000.0
        except Exception:
            return None

    def update_bgm_segment(self):
        if not self.bgm_playing or self.bgm_segment_end is None:
            return False
        position = self.get_bgm_position()
        if position is None or position < self.bgm_segment_end:
            return False
        if self.bgm_segment_loop:
            return self.play_bgm_segment(
                self.current_bgm_ref,
                self.bgm_segment_start,
                self.bgm_segment_end,
                loop=True,
            )
        self.stop_bgm()
        return True

    def switch_bgm(self, bgm_path=None, fadeout_ms=350, fadein_ms=350):
        target_ref = bgm_path if bgm_path else self.bgm_path
        if not target_ref:
            return False
        resolved = self._resolve_audio_path(target_ref)
        if not resolved:
            print(f"[audio] bgm file not found: {target_ref}")
            return False
        if self.bgm_playing and self.current_bgm_resolved == resolved:
            self.bgm_path = target_ref
            self.current_bgm_ref = target_ref
            return True
        try:
            if self.bgm_playing and int(fadeout_ms or 0) > 0:
                pygame.mixer.music.fadeout(max(0, int(fadeout_ms or 0)))
            self.bgm_path = target_ref
            return self.play_bgm(target_ref, fade_ms=fadein_ms, restart=True)
        except Exception as exc:
            print(f"[audio] bgm switch failed: {exc}")
            return False

    def stop_bgm(self, fadeout_ms=0):
        try:
            if int(fadeout_ms or 0) > 0:
                pygame.mixer.music.fadeout(max(0, int(fadeout_ms or 0)))
            else:
                pygame.mixer.music.stop()
            self.bgm_playing = False
            self.current_bgm_ref = None
            self.current_bgm_resolved = None
            self.bgm_segment_start = 0.0
            self.bgm_segment_end = None
            self.bgm_segment_loop = False
            return True
        except Exception as exc:
            print(f"[audio] bgm stop failed: {exc}")
            return False

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

        resolved = self._resolve_audio_path(path)

        if not resolved:
            print(f"[audio] sfx file not found: {path}")
            return

        try:
            sound = self.sfx_cache.get(sfx_id)

            if sound is None:
                sound = pygame.mixer.Sound(resolved)
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
