"""
Tests pour core/config.py — validation, load/save, regex cache, logging.
"""
import json
import os
import time
import threading

import pytest

from core.config import (
    DEFAULT_CONFIG, VALID_MODELS, VALID_HOTKEYS, VALID_THEMES,
    VALID_DEVICES, VALID_LANGUAGES, VALID_POSITIONS, VALID_UI_LANGS,
    MIN_W, MIN_H, MAX_WIN_W, MAX_WIN_H,
    validate_config, load_config, save_config,
    log_error, regex_cache, invalidate_regex_cache,
    CONFIG_FILE, LOG_FILE,
)


# ── validate_config ──────────────────────────────────────────────────────


class TestValidateConfig:
    """Tests pour validate_config()."""

    def test_valid_config_unchanged(self, default_config):
        """Une config valide ne doit pas être modifiée."""
        result = validate_config(default_config)
        assert result["model"] == "large-v3"
        assert result["hotkey"] == "f9"
        assert result["theme"] == "dark"

    def test_invalid_model_reset(self):
        """Un modèle invalide doit être remplacé par le défaut."""
        c = DEFAULT_CONFIG.copy()
        c["model"] = "inexistant"
        result = validate_config(c)
        assert result["model"] == DEFAULT_CONFIG["model"]

    def test_invalid_hotkey_reset(self):
        c = DEFAULT_CONFIG.copy()
        c["hotkey"] = "f99"
        result = validate_config(c)
        assert result["hotkey"] == DEFAULT_CONFIG["hotkey"]

    def test_invalid_theme_reset(self):
        c = DEFAULT_CONFIG.copy()
        c["theme"] = "neon"
        result = validate_config(c)
        assert result["theme"] == DEFAULT_CONFIG["theme"]

    def test_invalid_device_reset(self):
        c = DEFAULT_CONFIG.copy()
        c["device"] = "tpu"
        result = validate_config(c)
        assert result["device"] == DEFAULT_CONFIG["device"]

    def test_invalid_language_reset(self):
        c = DEFAULT_CONFIG.copy()
        c["language"] = "xx"
        result = validate_config(c)
        assert result["language"] == DEFAULT_CONFIG["language"]

    def test_invalid_position_reset(self):
        c = DEFAULT_CONFIG.copy()
        c["position"] = "milieu"
        result = validate_config(c)
        assert result["position"] == DEFAULT_CONFIG["position"]

    def test_invalid_ui_lang_reset(self):
        c = DEFAULT_CONFIG.copy()
        c["ui_lang"] = "jp"
        result = validate_config(c)
        assert result["ui_lang"] == DEFAULT_CONFIG["ui_lang"]

    def test_all_valid_models_accepted(self):
        for model in VALID_MODELS:
            c = DEFAULT_CONFIG.copy()
            c["model"] = model
            result = validate_config(c)
            assert result["model"] == model

    def test_all_valid_hotkeys_accepted(self):
        for hk in VALID_HOTKEYS:
            c = DEFAULT_CONFIG.copy()
            c["hotkey"] = hk
            result = validate_config(c)
            assert result["hotkey"] == hk

    # ── Macros validation ──

    def test_macros_valid_list(self):
        c = DEFAULT_CONFIG.copy()
        c["macros"] = [{"name": "test", "text": "hello"}]
        result = validate_config(c)
        assert len(result["macros"]) == 1

    def test_macros_invalid_not_list(self):
        c = DEFAULT_CONFIG.copy()
        c["macros"] = "not a list"
        result = validate_config(c)
        assert result["macros"] == []

    def test_macros_filters_invalid_entries(self):
        c = DEFAULT_CONFIG.copy()
        c["macros"] = [
            {"name": "ok", "text": "val"},       # valide
            {"name": 42, "text": "val"},          # name pas str
            {"other": "key"},                      # pas de name/text
            {"name": "ok2", "text": "val2"},      # valide
        ]
        result = validate_config(c)
        assert len(result["macros"]) == 2

    # ── Actions validation ──

    def test_actions_valid(self):
        c = DEFAULT_CONFIG.copy()
        c["actions"] = [{"name": "app", "path": "C:\\test.exe"}]
        result = validate_config(c)
        assert len(result["actions"]) == 1

    def test_actions_invalid_not_list(self):
        c = DEFAULT_CONFIG.copy()
        c["actions"] = 42
        result = validate_config(c)
        assert result["actions"] == []

    # ── Dictionary validation ──

    def test_dictionary_valid(self):
        c = DEFAULT_CONFIG.copy()
        c["dictionary"] = [{"wrong": "test", "correct": "Test"}]
        result = validate_config(c)
        assert len(result["dictionary"]) == 1

    def test_dictionary_filters_empty_wrong(self):
        c = DEFAULT_CONFIG.copy()
        c["dictionary"] = [
            {"wrong": "ok", "correct": "OK"},
            {"wrong": "   ", "correct": "spaces"},  # wrong est vide après strip
        ]
        result = validate_config(c)
        assert len(result["dictionary"]) == 1

    # ── Action trigger ──

    def test_action_trigger_empty_reset(self):
        c = DEFAULT_CONFIG.copy()
        c["action_trigger"] = "   "
        result = validate_config(c)
        assert result["action_trigger"] == "action"

    def test_action_trigger_not_string_reset(self):
        c = DEFAULT_CONFIG.copy()
        c["action_trigger"] = 123
        result = validate_config(c)
        assert result["action_trigger"] == "action"

    # ── Streaming ──

    def test_streaming_valid_bool(self):
        c = DEFAULT_CONFIG.copy()
        c["streaming"] = False
        result = validate_config(c)
        assert result["streaming"] is False

    def test_streaming_invalid_reset(self):
        c = DEFAULT_CONFIG.copy()
        c["streaming"] = "yes"
        result = validate_config(c)
        assert result["streaming"] is True  # défaut

    # ── Window dimensions ──

    def test_win_coords_float_to_int(self):
        c = DEFAULT_CONFIG.copy()
        c["win_x"] = 100.7
        c["win_y"] = 200.3
        result = validate_config(c)
        assert result["win_x"] == 100
        assert result["win_y"] == 200

    def test_win_coords_invalid_removed(self):
        c = DEFAULT_CONFIG.copy()
        c["win_x"] = "abc"
        result = validate_config(c)
        assert "win_x" not in result

    def test_win_w_valid(self):
        c = DEFAULT_CONFIG.copy()
        c["win_w"] = 800
        c["win_h"] = 400
        result = validate_config(c)
        assert result["win_w"] == 800
        assert result["win_h"] == 400

    def test_win_w_too_small_removed(self):
        c = DEFAULT_CONFIG.copy()
        c["win_w"] = 100  # < MIN_W (480)
        result = validate_config(c)
        assert "win_w" not in result

    def test_win_w_too_large_removed(self):
        c = DEFAULT_CONFIG.copy()
        c["win_w"] = 9999  # > MAX_WIN_W (4000)
        result = validate_config(c)
        assert "win_w" not in result

    def test_win_h_too_small_removed(self):
        c = DEFAULT_CONFIG.copy()
        c["win_h"] = 50  # < MIN_H (220)
        result = validate_config(c)
        assert "win_h" not in result


# ── save_config / load_config ────────────────────────────────────────────


class TestSaveLoadConfig:
    """Tests pour save_config() et load_config()."""

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        """Save puis load doit retourner la même config."""
        cfg_file = str(tmp_path / "config.json")
        monkeypatch.setattr("core.config.CONFIG_FILE", cfg_file)

        cfg = DEFAULT_CONFIG.copy()
        cfg["model"] = "tiny"
        cfg["language"] = "en"
        save_config(cfg)

        loaded = load_config()
        assert loaded["model"] == "tiny"
        assert loaded["language"] == "en"

    def test_load_missing_file_returns_default(self, tmp_path, monkeypatch):
        """Si le fichier n'existe pas, retourne la config par défaut."""
        cfg_file = str(tmp_path / "nonexistent.json")
        monkeypatch.setattr("core.config.CONFIG_FILE", cfg_file)

        loaded = load_config()
        assert loaded == DEFAULT_CONFIG

    def test_load_corrupted_json_returns_default(self, tmp_path, monkeypatch):
        """Un JSON corrompu doit retourner la config par défaut."""
        cfg_file = str(tmp_path / "bad.json")
        monkeypatch.setattr("core.config.CONFIG_FILE", cfg_file)
        with open(cfg_file, "w") as f:
            f.write("{invalid json!!!")

        loaded = load_config()
        assert loaded == DEFAULT_CONFIG

    def test_load_non_dict_json_returns_default(self, tmp_path, monkeypatch):
        """Un JSON qui n'est pas un dict doit retourner la config par défaut."""
        cfg_file = str(tmp_path / "list.json")
        monkeypatch.setattr("core.config.CONFIG_FILE", cfg_file)
        with open(cfg_file, "w") as f:
            json.dump([1, 2, 3], f)

        loaded = load_config()
        assert loaded == DEFAULT_CONFIG

    def test_load_fills_missing_keys(self, tmp_path, monkeypatch):
        """Les clés manquantes sont remplies par les défauts."""
        cfg_file = str(tmp_path / "partial.json")
        monkeypatch.setattr("core.config.CONFIG_FILE", cfg_file)
        with open(cfg_file, "w") as f:
            json.dump({"model": "tiny"}, f)

        loaded = load_config()
        assert loaded["model"] == "tiny"
        assert loaded["hotkey"] == DEFAULT_CONFIG["hotkey"]  # rempli

    def test_save_atomic_no_leftover_tmp(self, tmp_path, monkeypatch):
        """Après save, le fichier .tmp ne doit plus exister."""
        cfg_file = str(tmp_path / "config.json")
        monkeypatch.setattr("core.config.CONFIG_FILE", cfg_file)

        save_config(DEFAULT_CONFIG.copy())
        assert not os.path.exists(cfg_file + ".tmp")
        assert os.path.exists(cfg_file)

    def test_save_invalidates_regex_cache(self, tmp_path, monkeypatch):
        """save_config doit invalider le cache regex."""
        cfg_file = str(tmp_path / "config.json")
        monkeypatch.setattr("core.config.CONFIG_FILE", cfg_file)

        regex_cache["macros"] = [("fake", "cache")]
        save_config(DEFAULT_CONFIG.copy())
        assert regex_cache["macros"] is None


# ── regex_cache ──────────────────────────────────────────────────────────


class TestRegexCache:

    def test_invalidate_sets_all_to_none(self):
        regex_cache["macros"] = [1, 2, 3]
        regex_cache["actions"] = [4, 5]
        regex_cache["dictionary"] = [6]
        invalidate_regex_cache()
        assert regex_cache["macros"] is None
        assert regex_cache["actions"] is None
        assert regex_cache["dictionary"] is None


# ── log_error ────────────────────────────────────────────────────────────


class TestLogError:

    def test_log_message(self, tmp_path, monkeypatch):
        """log_error écrit le message dans le fichier log."""
        log_file = str(tmp_path / "test.log")
        monkeypatch.setattr("core.config.LOG_FILE", log_file)

        log_error(msg="Test message 123")

        content = open(log_file).read()
        assert "Test message 123" in content

    def test_log_exception(self, tmp_path, monkeypatch):
        """log_error écrit le traceback d'une exception."""
        log_file = str(tmp_path / "test.log")
        monkeypatch.setattr("core.config.LOG_FILE", log_file)

        try:
            raise ValueError("test error")
        except ValueError as e:
            log_error(e, "contexte")

        content = open(log_file).read()
        assert "contexte" in content
        assert "ValueError" in content

    def test_log_thread_safe(self, tmp_path, monkeypatch):
        """log_error doit être appelable depuis plusieurs threads sans crash."""
        log_file = str(tmp_path / "test.log")
        monkeypatch.setattr("core.config.LOG_FILE", log_file)

        errors = []

        def _log_many(n):
            try:
                for i in range(50):
                    log_error(msg=f"Thread {n} msg {i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_log_many, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        content = open(log_file).read()
        assert "Thread 0" in content
        assert "Thread 3" in content
