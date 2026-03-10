"""
Whisper Hélio — Configuration, logging, validation

Ce module gère :
- Chemins de configuration et de log
- Configuration par défaut et constantes de validation
- Chargement / sauvegarde atomique de la config JSON
- Logging d'erreurs avec rotation automatique
- Cache regex (invalidé à chaque sauvegarde)

Aucune dépendance vers le reste de l'application (module autonome).
"""

import json
import os
import time
import traceback
import threading
from pathlib import Path


# ── Chemins ───────────────────────────────────────────────────────────────
HOME_DIR    = Path.home()
BASE_DIR    = Path(__file__).resolve().parent.parent   # dossier du projet (parent de core/)
CONFIG_FILE = str(HOME_DIR / "whisper_helio_config.json")
LOG_FILE    = str(HOME_DIR / "whisper_helio_crash.log")


# ── Constantes de dimensions fenêtre (utilisées par validate_config) ──────
MAX_WIN_W = 4000
MAX_WIN_H = 3000
MIN_W = 480
MIN_H = 220


# ── Configuration par défaut ──────────────────────────────────────────────
DEFAULT_CONFIG = {
    "theme": "dark",
    "model": "large-v3",
    "device": "auto",
    "hotkey": "f9",
    "language": "fr",
    "ui_lang": "fr",
    "position": "bas-gauche",
    "macros": [],
    "action_trigger": "action",
    "actions": [],
    "dictionary": [],
    "streaming": True,          # Aperçu temps réel (modèle tiny en parallèle)
}


# ── Constantes de validation ──────────────────────────────────────────────
VALID_MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3", "large-v3-turbo"]
VALID_HOTKEYS = ["f9", "f10", "f11", "f12", "f8", "f7", "f6", "f5",
                  "pause", "scroll_lock", "insert",
                  "mouse_x1", "mouse_x2"]
VALID_THEMES = ["dark", "light"]
VALID_DEVICES = ["auto", "cuda", "cpu"]
VALID_LANGUAGES = ["fr", "en", "es", "de", "it", "pt", "nl"]
VALID_POSITIONS = ["bas-gauche", "bas-droite", "haut-gauche", "haut-droite", "centre"]
VALID_UI_LANGS = ["fr", "en", "de"]


# ── Validation ────────────────────────────────────────────────────────────

def validate_config(c):
    """Valide et corrige les valeurs de configuration."""
    _enum_checks = {
        "model":    VALID_MODELS,
        "hotkey":   VALID_HOTKEYS,
        "theme":    VALID_THEMES,
        "device":   VALID_DEVICES,
        "language": VALID_LANGUAGES,
        "position": VALID_POSITIONS,
        "ui_lang":  VALID_UI_LANGS,
    }
    for key, valid in _enum_checks.items():
        if c.get(key) not in valid:
            c[key] = DEFAULT_CONFIG[key]

    # Validation macros (doit être une liste de dicts)
    if not isinstance(c.get("macros"), list):
        c["macros"] = []
    else:
        c["macros"] = [
            m for m in c["macros"]
            if isinstance(m, dict)
            and isinstance(m.get("name"), str)
            and isinstance(m.get("text"), str)
        ]

    # Validation action_trigger
    if not isinstance(c.get("action_trigger"), str) or not c["action_trigger"].strip():
        c["action_trigger"] = DEFAULT_CONFIG["action_trigger"]

    # Validation actions (doit être une liste de dicts avec name + path)
    if not isinstance(c.get("actions"), list):
        c["actions"] = []
    else:
        c["actions"] = [
            a for a in c["actions"]
            if isinstance(a, dict)
            and isinstance(a.get("name"), str)
            and isinstance(a.get("path"), str)
        ]

    # Validation dictionary (liste de dicts avec "wrong" + "correct")
    if not isinstance(c.get("dictionary"), list):
        c["dictionary"] = []
    else:
        c["dictionary"] = [
            d for d in c["dictionary"]
            if isinstance(d, dict)
            and isinstance(d.get("wrong"), str)
            and isinstance(d.get("correct"), str)
            and d["wrong"].strip()
        ]

    # Validation streaming (booléen)
    if not isinstance(c.get("streaming"), bool):
        c["streaming"] = DEFAULT_CONFIG["streaming"]

    # Validation des coordonnées fenêtre (float → int pour éviter TclError geometry)
    for key in ["win_x", "win_y"]:
        if key in c:
            if not isinstance(c[key], (int, float)):
                del c[key]
            else:
                c[key] = int(c[key])

    # Validation des dimensions fenêtre avec limites min/max
    if "win_w" in c:
        if not isinstance(c["win_w"], (int, float)) or not (MIN_W <= c["win_w"] <= MAX_WIN_W):
            del c["win_w"]
        else:
            c["win_w"] = int(c["win_w"])
    if "win_h" in c:
        if not isinstance(c["win_h"], (int, float)) or not (MIN_H <= c["win_h"] <= MAX_WIN_H):
            del c["win_h"]
        else:
            c["win_h"] = int(c["win_h"])

    return c


# ── Chargement / sauvegarde ───────────────────────────────────────────────

def load_config():
    """Charge la configuration depuis le fichier JSON."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                c = json.load(f)
                if not isinstance(c, dict):
                    return DEFAULT_CONFIG.copy()
                for k, v in DEFAULT_CONFIG.items():
                    if k not in c:
                        c[k] = v
                return validate_config(c)
        except (json.JSONDecodeError, IOError, OSError) as e:
            # Ne pas rester silencieux — logger pour diagnostiquer les configs corrompues
            try:
                log_error(e, f"Config corrompue ({CONFIG_FILE}) — reset aux valeurs par défaut")
            except Exception:
                pass   # log_error peut échouer au tout premier appel
    return DEFAULT_CONFIG.copy()


# ── Log erreurs ───────────────────────────────────────────────────────────
_LOG_MAX_SIZE = 5 * 1024 * 1024   # 5 Mo max — au-delà, le fichier est tronqué


def _rotate_log_if_needed():
    """Tronque le fichier log s'il dépasse _LOG_MAX_SIZE."""
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > _LOG_MAX_SIZE:
            # Garder les derniers 2 Mo (les erreurs récentes)
            with open(LOG_FILE, "rb") as f:
                f.seek(-2 * 1024 * 1024, 2)
                tail = f.read()
            with open(LOG_FILE, "wb") as f:
                f.write(b"[... log tronque ...]\n")
                f.write(tail)
    except (IOError, OSError):
        pass


_log_lock = threading.Lock()
_last_rotate_check = [0.0]   # timestamp du dernier check rotation


def log_error(e=None, msg=None):
    """Enregistre une erreur dans le fichier log (avec rotation à 5 Mo)."""
    try:
        with _log_lock:
            # Vérifier la rotation au plus toutes les 60 secondes
            _now = time.time()
            if _now - _last_rotate_check[0] > 60:
                _last_rotate_check[0] = _now
                _rotate_log_if_needed()
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                header = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                if msg:
                    f.write(header + msg + "\n")
                if e:
                    if not msg:
                        f.write(header)
                    traceback.print_exception(type(e), e, e.__traceback__, file=f)
    except (IOError, OSError):
        pass


def log_exception(exc_type, exc_value, exc_tb):
    """Hook pour les exceptions non catchées."""
    try:
        with _log_lock:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERREUR NON CATCHEE :\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except (IOError, OSError):
        pass


# ── Cache regex (invalidé à chaque save_config) ──────────────────────────
regex_cache = {
    "macros":     None,   # list of (pattern_compiled, replacement)
    "actions":    None,   # list of (pattern_compiled, name, kind, value)
    "dictionary": None,   # list of (pattern_compiled, correct)
}


def invalidate_regex_cache():
    """Invalide le cache regex — appelé après chaque sauvegarde config."""
    regex_cache["macros"]     = None
    regex_cache["actions"]    = None
    regex_cache["dictionary"] = None


def save_config(cfg):
    """Sauvegarde la configuration de manière atomique."""
    temp_file = CONFIG_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, CONFIG_FILE)
        invalidate_regex_cache()
    except Exception as e:
        log_error(e, "save_config")
        try: os.unlink(temp_file)
        except OSError: pass
