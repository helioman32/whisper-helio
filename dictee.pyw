"""
Whisper Hélio v1.4b — Dictée vocale Windows 100% offline
Basé sur OpenAI Whisper / faster-whisper

Auteur : Hélio, Bretagne (France)
Projet Seattle (USA) 2028

Nouveautés v1.4b :
- Minimisation WinAPI : bouton − envoie l'app dans la barre des tâches Windows
- Icône correcte au deiconify : restauration propre depuis la taskbar
- Mode compact (VU-mètre seul) : accessible par double-clic sur le header
- Dictionnaire avec lignes alternées : meilleure lisibilité
- Harmonisation UI/UX des fenêtres Macros / Actions / Dictionnaire
"""

import tkinter as tk
from tkinter import ttk
import threading
import os
import time
import sys
import ctypes
from pathlib import Path

# ── AppUserModelID — DOIT être défini avant toute fenêtre ────────────────
# Sans cet ID, Windows associe l'icône au processus Python générique
# et affiche l'icône Python dans la taskbar au lieu de whisper_helio.ico
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "HelioDL.WhisperHelio.v14b"
    )
except Exception:
    pass

# ── DPI Awareness (avant création fenêtre) ────────────────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════
# SPLASH SCREEN - Fenetre temporaire pendant le chargement des modules
# ══════════════════════════════════════════════════════════════════════════
_splash = tk.Tk()
_splash.title("Whisper Hélio")
_splash.overrideredirect(True)
_splash.attributes("-topmost", True)
_sw, _sh = _splash.winfo_screenwidth(), _splash.winfo_screenheight()
_splash.geometry(f"400x160+{(_sw-400)//2}+{(_sh-160)//2}")
_splash.configure(bg="#1a1a2e")

_splash_frame = tk.Frame(_splash, bg="#1a1a2e", highlightbackground="#2ecc71", highlightthickness=2)
_splash_frame.pack(fill="both", expand=True)
tk.Label(_splash_frame, text="Whisper Hélio v1.4b", font=("Segoe UI", 18, "bold"), fg="#2ecc71", bg="#1a1a2e").pack(pady=(20,5))
_splash_status = tk.StringVar(value="Demarrage...")
tk.Label(_splash_frame, textvariable=_splash_status, font=("Segoe UI", 10), fg="white", bg="#1a1a2e").pack(pady=5)
ttk.Style().configure("g.Horizontal.TProgressbar", troughcolor='#2d2d44', background='#2ecc71')
_splash_progress = ttk.Progressbar(_splash_frame, style="g.Horizontal.TProgressbar", length=300, mode='determinate')
_splash_progress.pack(pady=10)
_splash.update()

def _update_splash(msg, val):
    try:
        _splash_status.set(msg)
        _splash_progress['value'] = val
        _splash.update()
    except Exception:
        pass

# Charger les modules avec progression
_update_splash("Chargement audio...", 15)
import sounddevice as sd
import numpy as np

_update_splash("Chargement clavier...", 30)
import keyboard
import pyperclip
import pyautogui

_update_splash("Chargement Whisper...", 50)
import json
import math
import re
import socket
import subprocess
import ctypes.wintypes
import traceback
import webbrowser
import gc
import signal
from tkinter import filedialog
from faster_whisper import WhisperModel

_update_splash("Modules charges!", 70)

# Vérification version Python
if sys.version_info < (3, 8):
    _splash.destroy()
    import tkinter.messagebox as _mb
    _mb.showerror("Whisper Hélio", "Python 3.8+ requis — installez Python 3.8 ou plus récent.")
    sys.exit(1)

# FERMER LE SPLASH AVANT DE CREER LA FENETRE PRINCIPALE
_update_splash("Lancement interface...", 90)
time.sleep(0.3)
_splash.withdraw()  # Cacher d'abord, détruire plus tard

# ── Désactiver la pause pyautogui ─────────────────────────────────────────
pyautogui.PAUSE = 0

# ── Constantes de couleurs ────────────────────────────────────────────────
COLOR_GREEN = "#2ecc71"
COLOR_GREEN_HOVER = "#27ae60"
COLOR_RED = "#e74c3c"
COLOR_RED_DARK = "#c0392b"
COLOR_ORANGE = "#f39c12"
COLOR_PURPLE = "#7c3aed"
COLOR_BLUE = "#3498db"
COLOR_BLUE_DARK = "#2980b9"
COLOR_WHITE = "white"

# ── Constantes numériques ─────────────────────────────────────────────────
LOCK_PORT = 47899
SAMPLE_RATE = 16000
MAX_RECORD_SECONDS = 120
MIN_AUDIO_SAMPLES = 8000
POLL_INTERVAL = 0.015
DEBOUNCE_DELAY = 0.3
PASTE_DELAY = 0.05
VU_REFRESH_MS = 33
ROUNDED_DELAY_MS = 50
WAVE_SPEED = 0.06
VU_DECAY = 0.82
CORNER_RADIUS = 18
AUDIO_BLOCKSIZE = 4096
VAD_THRESHOLD = 0.01
MAX_WIN_W = 4000
MAX_WIN_H = 3000
MIN_W = 480
MIN_H = 220

# ── Constantes mode réunion ───────────────────────────────────────────────
MEETING_SILENCE_THRESHOLD = 1.2   # secondes de silence pour couper (assez long pour les pauses naturelles)
MEETING_MAX_DURATION      = 25.0  # secondes max sans coupure
MEETING_POLL              = 0.05  # intervalle de vérification
MEETING_MIN_VOICE_DURATION = 0.8  # durée min de parole avant de couper (évite segments trop courts)

# ── PayPal ────────────────────────────────────────────────────────────────
PAYPAL_URL = "https://www.paypal.com/paypalme/heliostmalo"

# ── Instance unique ───────────────────────────────────────────────────────
_lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
_lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    _lock_socket.bind(("127.0.0.1", LOCK_PORT))
except OSError:
    sys.exit(0)

# ── Config ────────────────────────────────────────────────────────────────
# pathlib.Path : gère nativement les espaces, accents et chemins UNC Windows
HOME_DIR    = Path.home()
BASE_DIR    = Path(__file__).resolve().parent   # dossier du .pyw
CONFIG_FILE = str(HOME_DIR / "whisper_helio_config.json")
LOG_FILE    = str(HOME_DIR / "whisper_helio_crash.log")

DEFAULT_CONFIG = {
    "theme": "dark",
    "model": "large-v3",
    "device": "auto",
    "hotkey": "f9",
    "language": "fr",
    "ui_lang": "fr",
    "position": "bas-gauche",
    "macro_trigger": "macro",
    "macros": [],
    "action_trigger": "action",
    "actions": [],
    "dictionary": []
}

# ── Constantes de validation ──────────────────────────────────────────────
VALID_MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3", "large-v3-turbo"]
VALID_HOTKEYS = ["f9", "f10", "f11", "f12", "mouse_x1", "mouse_x2"]
VALID_THEMES = ["dark", "light"]
VALID_DEVICES = ["auto", "cuda", "cpu"]
VALID_LANGUAGES = ["fr", "en", "es", "de", "it", "pt", "nl"]
VALID_POSITIONS = ["bas-gauche", "bas-droite", "haut-gauche", "haut-droite", "centre"]
VALID_UI_LANGS = ["fr", "en", "de"]

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
    
    # Validation macro_trigger
    if not isinstance(c.get("macro_trigger"), str) or not c["macro_trigger"].strip():
        c["macro_trigger"] = DEFAULT_CONFIG["macro_trigger"]
    
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
    
    # Validation des coordonnées fenêtre
    for key in ["win_x", "win_y"]:
        if key in c and not isinstance(c[key], (int, float)):
            del c[key]
    
    # Validation des dimensions fenêtre avec limites min/max
    if "win_w" in c:
        if not isinstance(c["win_w"], (int, float)) or not (MIN_W <= c["win_w"] <= MAX_WIN_W):
            del c["win_w"]
    if "win_h" in c:
        if not isinstance(c["win_h"], (int, float)) or not (MIN_H <= c["win_h"] <= MAX_WIN_H):
            del c["win_h"]
    
    return c

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
        except (json.JSONDecodeError, IOError, OSError):
            pass
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

def log_error(e=None, msg=None):
    """Enregistre une erreur dans le fichier log (avec rotation à 5 Mo)."""
    try:
        _rotate_log_if_needed()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            header = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
            if msg:
                f.write(header + msg + "\n")
            elif e:
                f.write(header)
            if e:
                traceback.print_exc(file=f)
    except (IOError, OSError):
        pass

def log_exception(exc_type, exc_value, exc_tb):
    """Hook pour les exceptions non catchées."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERREUR NON CATCHEE :\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except (IOError, OSError):
        pass

sys.excepthook = log_exception

# ── Cache regex (invalidé à chaque save_config) ──────────────────────────
_regex_cache = {
    "macros":     None,   # list of (pattern_compiled, replacement)
    "actions":    None,   # list of (pattern_compiled, name, kind, value)
    "dictionary": None,   # list of (pattern_compiled, correct)
}

def _invalidate_regex_cache():
    """Invalide le cache regex — appelé après chaque sauvegarde config."""
    _regex_cache["macros"]     = None
    _regex_cache["actions"]    = None
    _regex_cache["dictionary"] = None

def save_config(cfg):
    """Sauvegarde la configuration de manière atomique."""
    try:
        temp_file = CONFIG_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, CONFIG_FILE)
        _invalidate_regex_cache()
    except Exception as e:
        log_error(e)

config = load_config()

# ── Traductions interface ──────────────────────────────────────────────────
TRANSLATIONS = {
    "fr": {
        "title": "Whisper Hélio v1.4b",
        "loading": "Chargement du modele...",
        "loading_long": "Chargement (peut prendre 30s au premier lancement)...",
        "init": "Initialisation ({i}/{n})...",
        "ready": "Pret — {hotkey} pour dicter",
        "recording": "Enregistrement...",
        "transcribing": "Transcription...",
        "meeting_on": "Mode reunion — enregistrement continu",
        "final_trans": "Transcription finale...",
        "settings": "Parametres",
        "hardware": "Materiel detecte : {hw}",
        "theme": "Theme",
        "model": "Modele Whisper",
        "device": "Device",
        "lang": "Langue dictee",
        "ui_lang": "Langue interface",
        "shortcut": "Raccourci",
        "position": "Position demarrage",
        "save": "  Sauvegarder  ",
        "restart_note": "Redemarrez l'app apres changement de modele/device",
        "thumb_back": "Bouton pouce arriere",
        "thumb_fwd": "Bouton pouce avant",
        "support": "Soutenir le projet",
        "no_mic": "Aucun microphone detecte. Branchez un micro et relancez.",
        "model_error": "Erreur chargement modele. Verifiez votre connexion.",
        "fallback": "Fallback vers {model}...",
        "macros": "Macros",
        "macro_trigger_label": "Mot declencheur",
        "macro_name": "Nom",
        "macro_text": "Texte",
        "macro_add": "+ Ajouter",
        "macro_delete": "Supprimer",
        "macro_save": "  Sauvegarder  ",
        "macro_title": "Gestionnaire de Macros",
        "macro_help": "Dites le mot declencheur suivi du nom. Ex: \"macro adresse\"",
        "actions_tab": "Actions",
        "macros_tab": "Macros texte",
        "action_trigger_label": "Mot declencheur actions",
        "action_name": "Nom vocal",
        "action_path": "Programme (.exe)",
        "action_add": "+ Ajouter action",
        "action_delete": "Supprimer",
        "action_save": "  Sauvegarder  ",
        "action_browse": "Parcourir...",
        "action_help": "Dites le mot d'action suivi du nom. Ex: \"action excel\"",
        "action_builtin": "Actions integrees (toujours disponibles)",
        "action_custom": "Mes actions personnalisees",
        "action_launched": "Lance : {name}",
        "action_not_found": "Programme introuvable : {name}",
        "dict_tab": "Dictionnaire",
        "dict_wrong": "Whisper transcrit",
        "dict_correct": "Corriger en",
        "dict_add": "+ Ajouter mot",
        "dict_delete": "Supprimer",
        "dict_help": "Corrigez les mots mal transcrits. Ex: \"bonjour\" → \"Bonjour !\"",
        "dict_example": "Exemples: noms propres, termes techniques, acronymes",
    },
    "en": {
        "title": "Whisper Hélio v1.4b",
        "loading": "Loading model...",
        "loading_long": "Loading (may take 30s on first launch)...",
        "init": "Initializing ({i}/{n})...",
        "ready": "Ready — {hotkey} to dictate",
        "recording": "Recording...",
        "transcribing": "Transcribing...",
        "meeting_on": "Meeting mode — continuous recording",
        "final_trans": "Final transcription...",
        "settings": "Settings",
        "hardware": "Detected hardware: {hw}",
        "theme": "Theme",
        "model": "Whisper model",
        "device": "Device",
        "lang": "Dictation language",
        "ui_lang": "Interface language",
        "shortcut": "Shortcut",
        "position": "Start position",
        "save": "  Save  ",
        "restart_note": "Restart the app after changing model/device",
        "thumb_back": "Thumb button back",
        "thumb_fwd": "Thumb button forward",
        "support": "Support the project",
        "no_mic": "No microphone detected. Connect a mic and restart.",
        "model_error": "Model loading error. Check your connection.",
        "fallback": "Fallback to {model}...",
        "macros": "Macros",
        "macro_trigger_label": "Trigger word",
        "macro_name": "Name",
        "macro_text": "Text",
        "macro_add": "+ Add",
        "macro_delete": "Delete",
        "macro_save": "  Save  ",
        "macro_title": "Macro Manager",
        "macro_help": "Say the trigger word followed by the name. Ex: \"macro address\"",
        "actions_tab": "Actions",
        "macros_tab": "Text Macros",
        "action_trigger_label": "Action trigger word",
        "action_name": "Voice name",
        "action_path": "Program (.exe)",
        "action_add": "+ Add action",
        "action_delete": "Delete",
        "action_save": "  Save  ",
        "action_browse": "Browse...",
        "action_help": "Say the action word followed by the name. Ex: \"action excel\"",
        "action_builtin": "Built-in actions (always available)",
        "action_custom": "My custom actions",
        "action_launched": "Launched: {name}",
        "action_not_found": "Program not found: {name}",
        "dict_tab": "Dictionary",
        "dict_wrong": "Whisper transcribes",
        "dict_correct": "Replace with",
        "dict_add": "+ Add word",
        "dict_delete": "Delete",
        "dict_help": "Fix misrecognized words. Ex: \"bonjour\" → \"Bonjour !\"",
        "dict_example": "Examples: proper names, technical terms, acronyms",
    },
    "de": {
        "title": "Whisper Hélio v1.4b",
        "loading": "Modell wird geladen...",
        "loading_long": "Laden (kann beim ersten Start 30s dauern)...",
        "init": "Initialisierung ({i}/{n})...",
        "ready": "Bereit — {hotkey} zum Diktieren",
        "recording": "Aufnahme...",
        "transcribing": "Transkription...",
        "meeting_on": "Besprechungsmodus — kontinuierliche Aufnahme",
        "final_trans": "Letzte Transkription...",
        "settings": "Einstellungen",
        "hardware": "Erkannte Hardware: {hw}",
        "theme": "Design",
        "model": "Whisper-Modell",
        "device": "Geraet",
        "lang": "Diktiersprache",
        "ui_lang": "Oberflaechensprache",
        "shortcut": "Tastenkuerzel",
        "position": "Startposition",
        "save": "  Speichern  ",
        "restart_note": "App nach Modell-/Geraeteaenderung neu starten",
        "thumb_back": "Daumentaste hinten",
        "thumb_fwd": "Daumentaste vorne",
        "support": "Projekt unterstuetzen",
        "no_mic": "Kein Mikrofon erkannt. Schliessen Sie ein Mikrofon an.",
        "model_error": "Fehler beim Laden. Prufen Sie Ihre Verbindung.",
        "fallback": "Fallback zu {model}...",
        "macros": "Makros",
        "macro_trigger_label": "Ausloesewort",
        "macro_name": "Name",
        "macro_text": "Text",
        "macro_add": "+ Hinzufuegen",
        "macro_delete": "Loeschen",
        "macro_save": "  Speichern  ",
        "macro_title": "Makro-Verwaltung",
        "macro_help": "Sagen Sie das Ausloesewort gefolgt vom Namen. Bsp: \"makro adresse\"",
        "actions_tab": "Aktionen",
        "macros_tab": "Text-Makros",
        "action_trigger_label": "Aktions-Ausloesewort",
        "action_name": "Sprachname",
        "action_path": "Programm (.exe)",
        "action_add": "+ Aktion hinzufuegen",
        "action_delete": "Loeschen",
        "action_save": "  Speichern  ",
        "action_browse": "Durchsuchen...",
        "action_help": "Sagen Sie das Aktionswort gefolgt vom Namen. Bsp: \"aktion excel\"",
        "action_builtin": "Eingebaute Aktionen (immer verfuegbar)",
        "action_custom": "Meine eigenen Aktionen",
        "action_launched": "Gestartet: {name}",
        "action_not_found": "Programm nicht gefunden: {name}",
        "dict_tab": "Woerterbuch",
        "dict_wrong": "Whisper schreibt",
        "dict_correct": "Ersetzen durch",
        "dict_add": "+ Wort hinzufuegen",
        "dict_delete": "Loeschen",
        "dict_help": "Falsch erkannte Woerter korrigieren. Bsp: \"bonjour\" → \"Bonjour !\"",
        "dict_example": "Beispiele: Eigennamen, Fachbegriffe, Akronyme",
    },
}

_tr_cache = {}   # {(lang, key): text_sans_kwargs} — vidé au changement de langue

def tr(key, **kwargs):
    """Retourne la traduction pour la clé donnée (avec cache pour les appels sans kwargs)."""
    lang = config["ui_lang"]
    if not kwargs:
        cached = _tr_cache.get((lang, key))
        if cached is not None:
            return cached
    t = TRANSLATIONS.get(lang, TRANSLATIONS["fr"])
    text = t.get(key, TRANSLATIONS["fr"].get(key, key))
    if not kwargs:
        _tr_cache[(lang, key)] = text
        return text
    return text.format_map(kwargs)

# ── Détection matériel ────────────────────────────────────────────────────
def init_device():
    """Initialise le device et détecte le matériel disponible."""
    dev = config["device"]
    if dev in ("cuda", "auto"):
        try:
            import ctranslate2 as _ct2
            gpu_count = _ct2.get_cuda_device_count()
            if gpu_count > 0:
                # Récupérer le nom du GPU via torch si disponible, sinon générique
                gpu_name = "NVIDIA GPU"
                try:
                    import torch
                    if torch.cuda.is_available():
                        gpu_name = torch.cuda.get_device_name(0)
                except Exception:
                    pass
                return "cuda", "float16", f"GPU: {gpu_name}"
            elif dev == "cuda":
                log_error(msg="CUDA configuré mais non disponible, fallback CPU")
                return "cpu", "int8", "CPU (CUDA indisponible)"
        except Exception:
            if dev == "cuda":
                return "cpu", "int8", "CPU (ctranslate2 CUDA non trouvé)"
    return "cpu", "int8", "CPU"

detected_device, detected_compute, hw_info = init_device()

# ── Thèmes ────────────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg": "#1c1c28",          # fond principal — proche du screenshot
        "bg_vu": "#1c1c28",       # VU-mètre : pas de boîte, même fond
        "fg": COLOR_WHITE,
        "fg2": "#777788",
        "fg_title": "#e0e0f0",    # titre Whisper Hélio
        "btn_fg": "#777788",
        "btn_icon_bg": "#2a2a3e", # fond boutons ronds header
        "link": "#777788",
        "vu_color": "#22d3ee",    # cyan du VU-mètre
        "footer_btn_bg": "#22d3ee",
        "footer_btn_fg": "#0a0a14",
    },
    "light": {
        "bg": "#f0f4f8",
        "bg_vu": "#f0f4f8",
        "fg": "#1a1a2e",
        "fg2": "#555577",
        "fg_title": "#1a1a2e",
        "btn_fg": "#555577",
        "btn_icon_bg": "#dde3ea",
        "link": "#555577",
        "vu_color": "#0891b2",
        "footer_btn_bg": "#0891b2",
        "footer_btn_fg": "#ffffff",
    }
}

# Cache du thème courant
_current_theme = [None]

def theme():
    """Retourne le thème courant (avec cache)."""
    theme_name = config["theme"]
    if _current_theme[0] is None or _current_theme[0][0] != theme_name:
        _current_theme[0] = (theme_name, THEMES[theme_name])
    return _current_theme[0][1]

# ── Position de démarrage ─────────────────────────────────────────────────
def get_start_pos(w, h, sw, sh, position):
    """Calcule la position de démarrage de la fenêtre."""
    margin = 20
    positions = {
        "bas-gauche": (margin, sh - h - margin),
        "bas-droite": (sw - w - margin, sh - h - margin),
        "haut-gauche": (margin, margin),
        "haut-droite": (sw - w - margin, margin),
        "centre": ((sw - w) // 2, (sh - h) // 2),
    }
    return positions.get(position, (margin, sh - h - margin))

# ── Fenêtre principale ────────────────────────────────────────────────────
root = tk.Tk()

# Maintenant on peut détruire le splash
try:
    _splash.destroy()
except Exception:
    pass

root.title("Whisper Hélio v1.4b")
try:
    root.iconbitmap(str(BASE_DIR / "whisper_helio.ico"))
except (tk.TclError, FileNotFoundError, OSError):
    pass

root.attributes("-topmost", True)
root.attributes("-alpha", 0.93)
root.overrideredirect(True)
root.configure(bg=theme()["bg"])

# ══════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════
# MINIMISATION TASKBAR — WinAPI directe sur root (v1.4b — sans proxy)
# ══════════════════════════════════════════════════════════════════════════
# Architecture v1.4b : on manipule DIRECTEMENT le HWND de root.
#   État normal   → WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE sur root
#                   → root invisible de la taskbar et Alt+Tab
#   Minimisation  → on retire WS_EX_TOOLWINDOW, on ajoute WS_EX_APPWINDOW
#                   → root apparaît dans la taskbar, puis ShowWindow(MINIMIZE)
#   Restauration  → ShowWindow(RESTORE), on remet WS_EX_TOOLWINDOW
#                   → root disparaît à nouveau de la taskbar
# Avantage : zéro fenêtre proxy, zéro doublon, comportement prévisible.
# ──────────────────────────────────────────────────────────────────────────
_u32      = ctypes.windll.user32
_ICO_PATH = str(BASE_DIR / "whisper_helio.ico")   # pathlib → str pour WinAPI

# Constantes WinAPI
_GWL_EXSTYLE      = -20
_WS_EX_APPWINDOW  = 0x00040000
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_NOACTIVATE = 0x08000000
_WM_SETICON       = 0x0080
_ICON_SMALL       = 0
_ICON_BIG         = 1
_IMAGE_ICON       = 1
_LR_LOADFROMFILE  = 0x00000010

# Cache HICON — chargés une seule fois pour éviter les fuites GDI
_cached_hicon_big   = [None]
_cached_hicon_small = [None]

_minimized  = [False]
_minimizing = [False]   # True pendant la séquence minimize → bloque <Map>
_saved_geom = [None]
_root_hwnd  = [None]   # HWND de root, mis en cache au premier accès

def _get_root_hwnd():
    """Retourne le HWND du cadre Windows de root (le vrai, visible en taskbar).
    Utilise wm_frame() en priorité — c'est le handle du cadre WM, celui que
    Windows utilise pour la taskbar. GetParent(winfo_id()) donne le HWND
    interne Tkinter qui n'est pas le même.
    """
    if not _root_hwnd[0]:
        try:
            frame = root.wm_frame()
            if frame and frame not in ("0x0", "0"):
                _root_hwnd[0] = int(frame, 16)
        except Exception:
            pass
        if not _root_hwnd[0]:
            try:
                _root_hwnd[0] = _u32.GetParent(root.winfo_id())
            except Exception:
                pass
    return _root_hwnd[0]

# ── Gestion du focus pour le collage post-transcription ──────────────────
_target_hwnd = [0]   # HWND de la fenêtre cible (capturé au déclenchement)

def _capture_target_window():
    """Mémorise la fenêtre active au moment du déclenchement du hotkey.
    Appelé depuis chargement() (thread BG) — utilise uniquement WinAPI,
    jamais Tkinter. _root_hwnd[0] est pré-caché depuis le thread principal.
    """
    try:
        hwnd = _u32.GetForegroundWindow()
        if hwnd and hwnd != _root_hwnd[0]:
            _target_hwnd[0] = hwnd
        else:
            _target_hwnd[0] = 0
    except Exception:
        _target_hwnd[0] = 0

def _restore_target_focus():
    """Remet le focus sur la fenêtre cible avant le collage.
    Utilise AttachThreadInput() pour contourner la restriction Windows qui
    bloque SetForegroundWindow() après ~200ms sans interaction utilisateur.
    Retourne True si le focus a été restauré.
    """
    target = _target_hwnd[0]
    if not target:
        return False
    try:
        if not _u32.IsWindow(target):
            _target_hwnd[0] = 0
            return False
        fg_hwnd = _u32.GetForegroundWindow()
        if fg_hwnd == target:
            return True
        fg_tid  = _u32.GetWindowThreadProcessId(fg_hwnd, None)
        our_tid = ctypes.windll.kernel32.GetCurrentThreadId()
        attached = (fg_tid != 0 and fg_tid != our_tid)
        if attached:
            _u32.AttachThreadInput(our_tid, fg_tid, True)
        try:
            _u32.SetForegroundWindow(target)
            _u32.BringWindowToTop(target)
        finally:
            # Détachement garanti même si SetForegroundWindow lève une exception
            if attached:
                _u32.AttachThreadInput(our_tid, fg_tid, False)
        return True
    except Exception:
        return False

def _apply_icon_to_hwnd(hwnd):
    """Applique whisper_helio.ico via toutes les méthodes disponibles.
    
    Triple méthode pour couvrir tous les cas Windows :
    1. root.iconbitmap()  → Tkinter met à jour son registre interne
    2. WM_SETICON SMALL   → icône 16px dans la barre de titre / taskbar
    3. WM_SETICON BIG     → icône 32px dans Alt+Tab
    """
    if not os.path.exists(_ICO_PATH):
        return

    # Méthode 1 : Tkinter natif (le plus fiable pour la taskbar Windows)
    try:
        root.iconbitmap(_ICO_PATH)
    except Exception:
        pass

    # Méthode 2+3 : WM_SETICON sur le HWND du cadre (renforce la méthode 1)
    if hwnd:
        try:
            # Charger une seule fois — évite les fuites GDI à chaque cycle
            if _cached_hicon_big[0] is None:
                _cached_hicon_big[0] = _u32.LoadImageW(
                    None, _ICO_PATH, _IMAGE_ICON, 32, 32, _LR_LOADFROMFILE)
            if _cached_hicon_small[0] is None:
                _cached_hicon_small[0] = _u32.LoadImageW(
                    None, _ICO_PATH, _IMAGE_ICON, 16, 16, _LR_LOADFROMFILE)
            if _cached_hicon_big[0]:
                _u32.SendMessageW(hwnd, _WM_SETICON, _ICON_BIG, _cached_hicon_big[0])
            if _cached_hicon_small[0]:
                _u32.SendMessageW(hwnd, _WM_SETICON, _ICON_SMALL, _cached_hicon_small[0])
        except Exception:
            pass

def minimize_to_taskbar():
    """Minimise root dans la taskbar.
    
    Séquence critique (ordre impératif) :
      1. alpha→0         : fenêtre invisible, pas de flash barre titre
      2. overrideredirect(False) : DÉCLENCHE <Map> → bloqué par _minimizing
      3. after(50ms) → WS_EX_APPWINDOW + icône + iconify()
         (le délai laisse Tkinter vider sa queue d'events avant iconify)
    """
    if _minimized[0] or _minimizing[0]:
        return

    _minimizing[0] = True   # bloque <Map> pendant la séquence
    _minimized[0]  = True
    _saved_geom[0] = (root.winfo_x(), root.winfo_y(),
                      root.winfo_width(), root.winfo_height())

    # Étape 1 : invisible (évite le flash de la barre titre Windows)
    root.attributes("-alpha", 0)
    root.update_idletasks()

    # Étape 2 : overrideredirect(False) → Windows peut maintenant créer
    # un bouton taskbar. DÉCLENCHE <Map> mais _minimizing le bloque.
    root.overrideredirect(False)

    def _do_iconify():
        """Appelé 50ms après overrideredirect(False) — events Tkinter vidés."""
        # Invalider le cache — overrideredirect change le HWND du cadre
        _root_hwnd[0] = None
        hwnd = _get_root_hwnd()

        # Appliquer WS_EX_APPWINDOW → force l'entrée dans la taskbar
        if hwnd:
            try:
                ex = _u32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
                ex = (ex & ~_WS_EX_TOOLWINDOW) | _WS_EX_APPWINDOW
                _u32.SetWindowLongW(hwnd, _GWL_EXSTYLE, ex)
            except Exception:
                pass

        # Appliquer l'icône AVANT iconify via iconbitmap (Tkinter natif)
        # Windows utilise cette icône pour le bouton taskbar qu'il va créer
        try:
            root.iconbitmap(_ICO_PATH)
        except Exception:
            pass

        # Minimiser — Windows crée le bouton taskbar avec l'icône déjà définie
        root.iconify()

        # Double application après iconify (certains Windows la réinitialisent)
        def _reinforce_icon():
            _root_hwnd[0] = None   # re-invalider — iconify peut changer le handle
            h = _get_root_hwnd()
            _apply_icon_to_hwnd(h)
            root.after(150, lambda: _minimizing.__setitem__(0, False))

        root.after(100, _reinforce_icon)

    root.after(50, _do_iconify)

def restore_from_taskbar(event=None):
    """Restaure root depuis la taskbar — appelé par <Map>."""
    # Bloquer pendant la séquence de minimisation
    if _minimizing[0] or not _minimized[0]:
        return
    _minimized[0] = False

    # Remettre overrideredirect (supprime la barre titre Windows)
    root.overrideredirect(True)
    _root_hwnd[0] = None   # HWND change à nouveau

    # Restaurer géométrie
    if _saved_geom[0]:
        x, y, w, h = _saved_geom[0]
    else:
        w = config.get("win_w", 900)
        h = config.get("win_h", 260)
        x = config.get("win_x", 100)
        y = config.get("win_y", 100)
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x  = max(0, min(x, sw - w))
    y  = max(0, min(y, sh - h))
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.attributes("-alpha", 0.93)
    root.attributes("-topmost", True)
    root.lift()
    root.update_idletasks()
    root.after(80, apply_rounded)
    try:
        root.focus_force()
    except Exception:
        pass

# Bind <Map> : déclenché quand l'utilisateur clique sur l'icône taskbar
root.bind("<Map>", restore_from_taskbar)

# Reconfigurer le style ttk pour root (le splash l'avait configuré avant)
style = ttk.Style(root)
style.theme_use('default')
style.configure("g.Horizontal.TProgressbar", troughcolor='#2d2d44', background='#2ecc71')
style.configure("TCombobox", fieldbackground="#2d2d44", background="#2d2d44")

screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()

saved_w = config.get("win_w", max(850, min(1000, int(screen_w * 0.65))))
saved_h = config.get("win_h", 260)

# Vérifier que la position est visible
if "win_x" in config and "win_y" in config:
    sx, sy = config["win_x"], config["win_y"]
    if sx < -50 or sx > screen_w - 50 or sy < -50 or sy > screen_h - 50:
        sx, sy = get_start_pos(saved_w, saved_h, screen_w, screen_h, config["position"])
else:
    sx, sy = get_start_pos(saved_w, saved_h, screen_w, screen_h, config["position"])

root.geometry(f"{saved_w}x{saved_h}+{sx}+{sy}")

# ── Variables globales pour cleanup ───────────────────────────────────────
stream = [None]
main_thread = [None]
_app_closing = [False]
_settings_window = [None]
_macros_window = [None]

# Verrou global anti-doublon transcription
# threading.Event partagé entre tous les threads (watchdog inclus)
# .is_set() = enregistrement en cours → toute ré-entrée bloquée
_recording_lock = threading.Event()

def on_close():
    """Ferme proprement l'application."""
    _app_closing[0] = True

    # Sauvegarder la position/taille (dimensions réelles, pas la taille compact)
    w_save = _full_width[0]  if _compact_mode[0] and _full_width[0]  else root.winfo_width()
    h_save = _full_height[0] if _compact_mode[0] and _full_height[0] else root.winfo_height()
    for k, v in (("win_x", root.winfo_x()), ("win_y", root.winfo_y()),
                 ("win_w", w_save), ("win_h", h_save)):
        config[k] = v
    save_config(config)

    # Libérer les ressources système
    try:
        keyboard.unhook_all()   # libérer tous les hooks clavier
    except Exception:
        pass
    for closer in (
        lambda: stream[0] and stream[0].stop(),
        lambda: stream[0] and stream[0].close(),
        lambda: _mouse_hook_handle[0] and _u32.UnhookWindowsHookEx(_mouse_hook_handle[0]),
        lambda: _lock_socket.close(),
    ):
        try:
            closer()
        except Exception:
            pass

    # Fermer les fenêtres Toplevel ouvertes
    for win_ref in (_settings_window, _macros_window):
        try:
            if win_ref[0] is not None and win_ref[0].winfo_exists():
                win_ref[0].destroy()
        except Exception:
            pass

    root.destroy()

# Gestion Ctrl+C
def signal_handler(sig, frame):
    """Gère le signal SIGINT (Ctrl+C)."""
    on_close()

try:
    signal.signal(signal.SIGINT, signal_handler)
except Exception:
    pass

root.protocol("WM_DELETE_WINDOW", on_close)

# ── Coins arrondis + NoActivate ───────────────────────────────────────────
def is_windows_11():
    """Détecte Windows 11."""
    try:
        return sys.getwindowsversion().build >= 22000
    except Exception:
        return False

def apply_rounded(event=None):
    """Applique les coins arrondis à la fenêtre.
    WS_EX_TOOLWINDOW : exclut root de la taskbar et Alt+Tab (état normal).
    WS_EX_NOACTIVATE : empêche root de prendre le focus au clic.
    Note : minimize_to_taskbar() retire temporairement TOOLWINDOW et ajoute
           APPWINDOW pour faire apparaître root dans la taskbar le temps de
           la minimisation. restore_from_taskbar() remet TOOLWINDOW.
    """
    try:
        HWND = ctypes.windll.user32.GetParent(root.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(HWND, _GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            HWND, _GWL_EXSTYLE,
            (style | _WS_EX_TOOLWINDOW | _WS_EX_NOACTIVATE)
        )

        # Toujours appliquer les coins arrondis (Windows 10 et 11)
        w, h = root.winfo_width(), root.winfo_height()
        if w > 10 and h > 10:
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, CORNER_RADIUS * 2, CORNER_RADIUS * 2)
            ctypes.windll.user32.SetWindowRgn(HWND, hrgn, True)
    except Exception:
        pass

_rounded_job = [None]
_last_rounded = [0]

def schedule_rounded(event=None):
    """Planifie l'application des coins arrondis avec debounce."""
    now = time.perf_counter()
    if now - _last_rounded[0] < 0.05:
        return
    _last_rounded[0] = now
    if _rounded_job[0]:
        root.after_cancel(_rounded_job[0])
    _rounded_job[0] = root.after(ROUNDED_DELAY_MS, apply_rounded)

root.after(150, apply_rounded)

# ── Redimensionnement / déplacement ──────────────────────────────────────
_resize_edge = [None]
BORDER = 6

# Constante globale pour les curseurs
CURSOR_MAP = {
    "e": "size_we", "w": "size_we", "n": "size_ns", "s": "size_ns",
    "ne": "size_ne_sw", "sw": "size_ne_sw", "nw": "size_nw_se", "se": "size_nw_se"
}

_current_cursor = [""]

def set_cursor(cursor):
    """Change le curseur seulement si différent."""
    if cursor != _current_cursor[0]:
        root.config(cursor=cursor)
        _current_cursor[0] = cursor

def get_edge(x, y, w, h):
    """Détermine le bord de la fenêtre sous le curseur."""
    edge = ""
    if y < BORDER:
        edge += "n"
    elif y > h - BORDER:
        edge += "s"
    if x < BORDER:
        edge += "w"
    elif x > w - BORDER:
        edge += "e"
    return edge or None

# Set pour les boutons (sera rempli après création)
_button_canvases = set()

def on_motion(e):
    """Gère le mouvement de la souris pour le curseur."""
    if e.widget in _button_canvases:
        set_cursor("hand2")
        return
    if hasattr(e.widget, '_is_clickable') and e.widget._is_clickable:
        set_cursor("hand2")
        return
    edge = get_edge(e.x_root - root.winfo_x(), e.y_root - root.winfo_y(),
                    root.winfo_width(), root.winfo_height())
    set_cursor(CURSOR_MAP.get(edge, "fleur"))

_last_click_time   = [0]
_last_click_widget = [None]

def on_press(e):
    """Gère le clic pour le redimensionnement/déplacement."""
    # Laisser passer le double-clic (deux clics < 400ms sur même widget)
    now = time.time()
    if now - _last_click_time[0] < 0.4 and e.widget is _last_click_widget[0]:
        _resize_edge[0] = None
        _last_click_time[0] = 0
        return
    _last_click_time[0]   = now
    _last_click_widget[0] = e.widget
    if e.widget in _button_canvases:
        _resize_edge[0] = None
        return
    if hasattr(e.widget, '_is_clickable') and e.widget._is_clickable:
        _resize_edge[0] = None
        return
    if e.widget not in (root, frame_top, frame_left, frame_center, frame_right,
                         vu_canvas, texte_label, donation_frame,
                         bottom_container, frame_links, sep_line):
        _resize_edge[0] = None
        return
    edge = get_edge(e.x_root - root.winfo_x(), e.y_root - root.winfo_y(),
                    root.winfo_width(), root.winfo_height())
    _resize_edge[0] = edge
    root._drag_x = e.x_root
    root._drag_y = e.y_root
    root._start_x = root.winfo_x()
    root._start_y = root.winfo_y()
    root._start_w = root.winfo_width()
    root._start_h = root.winfo_height()

_last_geometry_time = [0]

def on_drag(e):
    """Gère le drag pour redimensionner/déplacer."""
    if e.widget in _button_canvases:
        return
    if _resize_edge[0] is None and e.widget not in (root, frame_top, frame_left, frame_center,
                                                         frame_right, vu_canvas, texte_label,
                                                         donation_frame, bottom_container,
                                                         frame_links, sep_line):
        return
    
    # Throttle geometry updates
    now = time.perf_counter()
    if now - _last_geometry_time[0] < 0.016:
        return
    _last_geometry_time[0] = now
    
    dx = e.x_root - getattr(root, '_drag_x', e.x_root)
    dy = e.y_root - getattr(root, '_drag_y', e.y_root)
    edge = _resize_edge[0]
    x = getattr(root, '_start_x', root.winfo_x())
    y = getattr(root, '_start_y', root.winfo_y())
    w = getattr(root, '_start_w', root.winfo_width())
    h = getattr(root, '_start_h', root.winfo_height())
    
    if not edge:
        root.geometry(f"+{x + dx}+{y + dy}")
        return
    # En mode compact : pas de redimensionnement, seulement le drag
    if _compact_mode[0]:
        return
    nx, ny, nw, nh = x, y, w, h
    if "e" in edge:
        nw = max(MIN_W, min(MAX_WIN_W, w + dx))
    if "s" in edge:
        nh = max(MIN_H, min(MAX_WIN_H, h + dy))
    if "w" in edge:
        nw = max(MIN_W, min(MAX_WIN_W, w - dx))
        nx = x + (w - nw)
    if "n" in edge:
        nh = max(MIN_H, min(MAX_WIN_H, h - dy))
        ny = y + (h - nh)
    root.geometry(f"{nw}x{nh}+{nx}+{ny}")

root.bind("<Motion>", on_motion)
root.bind("<ButtonPress-1>", on_press)
root.bind("<B1-Motion>", on_drag)
root.bind("<ButtonRelease-1>", lambda e: _resize_edge.__setitem__(0, None))  # reset resize si release hors fenêtre

# ── Header — layout centré (style v2) ────────────────────────────────────
frame_top = tk.Frame(root, bg=theme()["bg"])
frame_top.pack(fill="x", padx=14, pady=(12, 0))

# ── Gauche : spacer invisible pour équilibrer le header ─────────────────
frame_left = tk.Frame(frame_top, bg=theme()["bg"], width=32)
frame_left.pack(side="left")
frame_left.pack_propagate(False)

# ── Centre : titre + hw + voyant + statut (tout centré) ──────────────────
frame_center = tk.Frame(frame_top, bg=theme()["bg"])
frame_center.pack(side="left", expand=True)

title_label = tk.Label(frame_center, text="Whisper Hélio v1.4b",
                       fg=theme().get("fg_title", COLOR_WHITE),
                       bg=theme()["bg"], font=("Segoe UI", 11, "bold"))
title_label.pack()

hw_label = tk.Label(frame_center, text=hw_info, fg=theme()["fg2"],
                    bg=theme()["bg"], font=("Segoe UI", 8))
hw_label.pack()

# Voyant + statut centrés sous hw_label
frame_statut = tk.Frame(frame_center, bg=theme()["bg"])
frame_statut.pack(pady=(3, 0))

voyant = tk.Canvas(frame_statut, width=12, height=12, bg=theme()["bg"], highlightthickness=0)
voyant.pack(side="left", pady=(1, 0))
cercle = voyant.create_oval(1, 1, 11, 11, fill=COLOR_GREEN, outline="")

statut_label = tk.Label(frame_statut, text=tr("loading"), fg=theme()["fg2"],
                        bg=theme()["bg"], font=("Segoe UI", 9))
statut_label.pack(side="left", padx=(5, 0))

# ── Droite : boutons icônes arrondis ─────────────────────────────────────
# Ordre visuel GAUCHE→DROITE : ⏺  🎙  ⚙  [espace]  −  ✕
# (frame_right est pack side="right", boutons pack side="left" = empilés de gauche à droite)
frame_right = tk.Frame(frame_top, bg=theme()["bg"])
frame_right.pack(side="right")

# ── 1. ⏺ Bouton Mode Réunion — le plus à gauche ──────────────────────────
btn_reunion = tk.Canvas(frame_right, width=26, height=26, bg=theme()["bg"], highlightthickness=0, cursor="hand2")
btn_reunion.pack(side="left", padx=(0, 3))
btn_reunion_bg  = btn_reunion.create_oval(2, 2, 24, 24, fill=COLOR_GREEN, outline="")
btn_reunion_txt = btn_reunion.create_text(13, 13, text="⏺", fill=COLOR_WHITE, font=("Segoe UI", 9))

def on_reunion_enter(e):
    btn_reunion.itemconfig(btn_reunion_bg, fill=COLOR_RED if mode_libre[0] else COLOR_GREEN_HOVER)
def on_reunion_leave(e):
    btn_reunion.itemconfig(btn_reunion_bg, fill=COLOR_RED if mode_libre[0] else COLOR_GREEN)
btn_reunion.bind("<Button-1>", lambda e: toggle_libre())
btn_reunion.bind("<Enter>",    on_reunion_enter)
btn_reunion.bind("<Leave>",    on_reunion_leave)

# ── 2. 🎙 Bouton Micro → ouvre Macros ────────────────────────────────────
btn_libre = tk.Canvas(frame_right, width=32, height=32, bg=theme()["bg"], highlightthickness=0, cursor="hand2")
btn_libre.pack(side="left", padx=3)
btn_libre_bg  = btn_libre.create_oval(2, 2, 30, 30, fill=theme().get("btn_icon_bg","#2a2a3e"), outline="")
btn_libre_txt = btn_libre.create_text(16, 16, text="🎙", fill=COLOR_WHITE, font=("Segoe UI", 11))

def on_libre_enter(e):
    t = theme()
    btn_libre.itemconfig(btn_libre_bg, fill=t.get("vu_color","#22d3ee"))
    btn_libre.itemconfig(btn_libre_txt, fill=t.get("footer_btn_fg","#0a0a14"))
def on_libre_leave(e):
    t = theme()
    btn_libre.itemconfig(btn_libre_bg, fill=t.get("btn_icon_bg","#2a2a3e"))
    btn_libre.itemconfig(btn_libre_txt, fill=COLOR_WHITE)
def on_libre_click(e):
    root.after(0, open_macros)
btn_libre.bind("<Button-1>", on_libre_click)
btn_libre.bind("<Enter>", on_libre_enter)
btn_libre.bind("<Leave>", on_libre_leave)

# ── 3. ⚙ Bouton Paramètres — engrenage dessiné ───────────────────────────
def _draw_gear(canvas, cx, cy, color):
    """Dessine un engrenage 8 dents sur le canvas. Retourne les IDs."""
    ids = []
    R_outer, R_inner, R_hole, N_teeth = 8.5, 6.2, 2.8, 8
    pts = []
    for i in range(N_teeth * 4):
        angle = math.pi * 2 * i / (N_teeth * 4) - math.pi / 2
        r = R_outer if i % 4 in (1, 2) else R_inner
        pts.extend([cx + r * math.cos(angle), cy + r * math.sin(angle)])
    ids.append(canvas.create_polygon(pts, fill=color, outline="", smooth=False))
    ids.append(canvas.create_oval(cx-R_hole, cy-R_hole, cx+R_hole, cy+R_hole,
                                  fill="", outline=color, width=2))
    return ids

btn_settings = tk.Canvas(frame_right, width=32, height=32, bg=theme()["bg"], highlightthickness=0, cursor="hand2")
btn_settings.pack(side="left", padx=3)
btn_settings_bg  = btn_settings.create_oval(2, 2, 30, 30, fill=theme().get("btn_icon_bg","#2a2a3e"), outline="")
btn_settings_txt = btn_settings.create_text(16, 16, text="⚙", fill=theme()["btn_fg"], font=("Segoe UI", 12))
_gear_color = theme()["btn_fg"]
_gear_ids   = _draw_gear(btn_settings, 16, 16, _gear_color)
btn_settings.delete(btn_settings_txt)
btn_settings_txt = None

def _redraw_gear(color):
    for gid in _gear_ids:
        try: btn_settings.delete(gid)
        except Exception: pass
    _gear_ids.clear()
    _gear_ids.extend(_draw_gear(btn_settings, 16, 16, color))

def on_settings_enter(e):
    btn_settings.itemconfig(btn_settings_bg, fill=COLOR_PURPLE)
    _redraw_gear(COLOR_WHITE)
def on_settings_leave(e):
    btn_settings.itemconfig(btn_settings_bg, fill=theme().get("btn_icon_bg","#2a2a3e"))
    _redraw_gear(theme()["btn_fg"])
btn_settings.bind("<Enter>", on_settings_enter)
btn_settings.bind("<Leave>", on_settings_leave)

# ── 4. − Bouton Minimiser [espace à gauche pour séparer du groupe] ────────
btn_minimize = tk.Canvas(frame_right, width=22, height=22, bg=theme()["bg"], highlightthickness=0, cursor="hand2")
btn_minimize.pack(side="left", padx=(10, 2))
btn_minimize_bg  = btn_minimize.create_oval(1, 1, 21, 21, fill=theme().get("btn_icon_bg","#2a2a3e"), outline="")
btn_minimize_txt = btn_minimize.create_text(11, 11, text="−", fill=theme()["btn_fg"], font=("Segoe UI", 10, "bold"))

def on_minimize_enter(e):
    btn_minimize.itemconfig(btn_minimize_bg, fill="#b45309")
    btn_minimize.itemconfig(btn_minimize_txt, fill=COLOR_WHITE)
def on_minimize_leave(e):
    btn_minimize.itemconfig(btn_minimize_bg, fill=theme().get("btn_icon_bg","#2a2a3e"))
    btn_minimize.itemconfig(btn_minimize_txt, fill=theme()["btn_fg"])
_compact_mode = [False]
_full_height   = [None]
_full_width    = [None]

def toggle_compact(event=None):
    """Bascule entre mode compact (vu-metre seul, 70px) et mode normal."""
    if _compact_mode[0]:
        # ── Restaurer mode normal ──
        _compact_mode[0] = False
        vu_canvas.unbind("<Double-Button-1>")
        # Remettre les limites normales avant de restaurer
        root.minsize(480, 220)
        root.maxsize(4000, 3000)
        vu_canvas.configure(height=56)
        # Forcer recréation des objets VU avec la hauteur normale (56px)
        vu_objects_created[0] = False
        vu_bg_objects.clear(); vu_bar_rects.clear()
        vu_bar_tops.clear();   vu_bar_bottoms.clear()
        vu_canvas.delete("all"); _vu_last_color[0] = None
        # frame_top doit revenir AVANT vu_canvas dans l'ordre pack
        frame_top.pack(fill="x", padx=14, pady=(12, 0), before=vu_canvas)
        texte_label.pack(fill="x", padx=10, pady=(4, 0))
        donation_frame.pack(fill="x", side="bottom", padx=14, pady=(0, 10))
        w = _full_width[0] or config.get("win_w", max(850, min(1000, int(root.winfo_screenwidth() * 0.65))))
        h = _full_height[0] or config.get("win_h", 260)
        root.geometry(f"{w}x{h}")
        root.after(80, apply_rounded)
    else:
        # ── Passer en mode compact ──
        _compact_mode[0] = True
        _full_height[0]  = root.winfo_height()
        _full_width[0]   = root.winfo_width()
        frame_top.pack_forget()
        texte_label.pack_forget()
        donation_frame.pack_forget()
        # Mode compact : 1/3 de la largeur, vu-mètre à 34px
        _compact_width = _full_width[0] // 3
        vu_canvas.configure(height=34)
        # Forcer recréation des objets VU avec la nouvelle hauteur (34px)
        vu_objects_created[0] = False
        vu_bg_objects.clear(); vu_bar_rects.clear()
        vu_bar_tops.clear();   vu_bar_bottoms.clear()
        vu_canvas.delete("all"); _vu_last_color[0] = None
        root.geometry(f"{_compact_width}x40")
        root.minsize(_compact_width, 40)
        root.maxsize(_compact_width, 40)
        root.after(80, apply_rounded)
        # Double-clic sur vu-metre = restaurer
        vu_canvas.bind("<Double-Button-1>", toggle_compact)

btn_minimize.bind("<Button-1>", lambda e: minimize_to_taskbar())
btn_minimize.bind("<Enter>",    on_minimize_enter)
btn_minimize.bind("<Leave>",    on_minimize_leave)

# Double-clic sur le header → toggle compact (mode VU-mètre seul)
# TOUS les widgets du header inclus pour couvrir toute la surface
for _dbl_w in (frame_top, frame_left, frame_center, frame_right,
               title_label, hw_label, frame_statut, statut_label, voyant):
    _dbl_w.bind("<Double-Button-1>", toggle_compact)

# ── 5. ✕ Bouton Fermer — le plus à droite ────────────────────────────────
btn_fermer = tk.Canvas(frame_right, width=22, height=22, bg=theme()["bg"], highlightthickness=0, cursor="hand2")
btn_fermer.pack(side="left", padx=(2, 0))
btn_fermer_bg  = btn_fermer.create_oval(1, 1, 21, 21, fill=theme().get("btn_icon_bg","#2a2a3e"), outline="")
btn_fermer_txt = btn_fermer.create_text(11, 11, text="✕", fill=theme()["btn_fg"], font=("Segoe UI", 8, "bold"))

def on_fermer_enter(e):
    btn_fermer.itemconfig(btn_fermer_bg, fill=COLOR_RED_DARK)
    btn_fermer.itemconfig(btn_fermer_txt, fill=COLOR_WHITE)
def on_fermer_leave(e):
    btn_fermer.itemconfig(btn_fermer_bg, fill=theme().get("btn_icon_bg","#2a2a3e"))
    btn_fermer.itemconfig(btn_fermer_txt, fill=theme()["btn_fg"])
btn_fermer.bind("<Button-1>", lambda e: on_close())
btn_fermer.bind("<Enter>",    on_fermer_enter)
btn_fermer.bind("<Leave>",    on_fermer_leave)

# ── Hotkey label ──────────────────────────────────────────────────────────
HOTKEY_LABELS = {"mouse_x1": "thumb_back", "mouse_x2": "thumb_fwd"}

def _hotkey_label():
    """Retourne le label du hotkey configuré."""
    h = config["hotkey"]
    if h in HOTKEY_LABELS:
        return tr(HOTKEY_LABELS[h])
    return h.upper()

mode_libre = [False]
hotkey_changed = [False]
_last_toggle_time = [0]

def toggle_libre():
    """Active/désactive le mode réunion avec debounce."""
    now = time.perf_counter()
    if now - _last_toggle_time[0] < DEBOUNCE_DELAY:
        return
    _last_toggle_time[0] = now
    mode_libre[0] = not mode_libre[0]
    if mode_libre[0]:
        btn_reunion.itemconfig(btn_reunion_bg, fill=COLOR_RED)
        set_statut_safe(tr("meeting_on"), COLOR_RED, COLOR_RED)
    else:
        btn_reunion.itemconfig(btn_reunion_bg, fill=COLOR_GREEN)
        set_statut_safe(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)
# Ajouter les boutons au set
_button_canvases = {btn_fermer, btn_settings, btn_libre, btn_reunion, btn_minimize}


# ── VU mètre — pleine largeur, barres cyan ───────────────────────────────
vu_canvas = tk.Canvas(root, height=56, bg=theme()["bg"], highlightthickness=0)
vu_canvas.pack(fill="x", padx=0, pady=(8, 0))

vu_level = [0.0]
wave_offset = [0.0]
NB_BARRES = 48          # plus de barres, style screenshot
VU_HEIGHT = 56
BAR_WIDTH = 3
BAR_RADIUS = BAR_WIDTH // 2 + 1
vu_width = [saved_w]

# Pré-calcul du profil bell (constant)
def bell(i, n):
    """Calcule le profil en cloche pour le VU-mètre."""
    x = (i - n / 2) / (n / 2)
    return math.exp(-x * x * 2.0)

BELL_PROFILE = [bell(i, NB_BARRES) for i in range(NB_BARRES)]

# Pré-calcul table sinus
SIN_TABLE_SIZE = 256
SIN_TABLE = [math.sin(i * 2 * math.pi / SIN_TABLE_SIZE) for i in range(SIN_TABLE_SIZE)]

def fast_sin(x):
    """Sinus rapide via table pré-calculée."""
    return SIN_TABLE[int(x * 40.74) & (SIN_TABLE_SIZE - 1)]

# Objets VU-mètre pré-créés
vu_objects_created = [False]
vu_bg_objects = []
vu_bar_rects = []
vu_bar_tops = []
vu_bar_bottoms = []
_vu_last_color = [None]   # cache couleur — évite 84 itemconfig inutiles à 30fps

def create_vu_objects():
    """Crée les objets du VU-mètre — ovale de fond + barres cyan dedans."""
    if vu_objects_created[0]:
        return

    w         = vu_width[0]
    h         = vu_canvas.winfo_height() or VU_HEIGHT   # hauteur réelle (compact=34, normal=56)
    t         = theme()
    vu_color  = t.get("vu_color", "#22d3ee")
    bg_color  = t.get("bg", "#1c1c28")

    # ── Ovale de fond (pill) centré ─────────────────────────────────────────
    pill_h    = h - 6          # hauteur de l'ovale
    pill_w    = min(w - 20, int(w * 0.72))   # largeur max 72% de la fenêtre
    ox        = (w - pill_w) // 2            # position x gauche
    oy        = (h - pill_h) // 2            # position y haut
    ox2       = ox + pill_w
    oy2       = oy + pill_h
    r_pill    = pill_h // 2    # rayon des coins = demi-hauteur → ovale parfait

    # Fond pill : 4 arcs + 1 rectangle central
    pill_bg = "#111120"  # fond légèrement plus sombre que le bg
    vu_bg_objects.append(vu_canvas.create_arc(ox, oy, ox + r_pill*2, oy2, start=90, extent=180, fill=pill_bg, outline=pill_bg))
    vu_bg_objects.append(vu_canvas.create_arc(ox2 - r_pill*2, oy, ox2, oy2, start=270, extent=180, fill=pill_bg, outline=pill_bg))
    vu_bg_objects.append(vu_canvas.create_rectangle(ox + r_pill, oy, ox2 - r_pill, oy2, fill=pill_bg, outline=pill_bg))

    # ── Barres dans la pill ─────────────────────────────────────────────────
    inner_margin = r_pill + 8    # laisser de la place dans les coins arrondis
    inner_w   = pill_w - inner_margin * 2
    inner_mid = h // 2
    # Adapter le nombre de barres à la place disponible
    nb        = max(4, min(NB_BARRES, (inner_w + 2) // (BAR_WIDTH + 2)))
    gap       = max(2, (inner_w - nb * BAR_WIDTH) // max(1, nb - 1))
    # Centrer mathématiquement dans la pill
    total_bars_w = nb * BAR_WIDTH + (nb - 1) * gap
    start_x   = ox + (pill_w - total_bars_w) // 2

    for i in range(nb):
        x1 = start_x + i * (BAR_WIDTH + gap)
        x2 = x1 + BAR_WIDTH
        tag = f"bar_{i}"
        vu_bar_rects.append(vu_canvas.create_rectangle(
            x1, inner_mid - 5, x2, inner_mid + 5, fill=vu_color, outline="", tags=tag))
        vu_bar_tops.append(vu_canvas.create_oval(
            x1, inner_mid - 5, x2, inner_mid - 5 + BAR_RADIUS * 2, fill=vu_color, outline="", tags=tag))
        vu_bar_bottoms.append(vu_canvas.create_oval(
            x1, inner_mid + 5 - BAR_RADIUS * 2, x2, inner_mid + 5, fill=vu_color, outline="", tags=tag))

    _vu_last_color[0] = None
    vu_objects_created[0] = True

def update_vu_objects():
    """Met à jour les positions et couleurs du VU-mètre (pleine largeur)."""
    if not vu_objects_created[0]:
        create_vu_objects()
        return

    w         = vu_width[0]
    h         = vu_canvas.winfo_height() or VU_HEIGHT   # hauteur réelle du canvas
    pill_w    = min(w - 20, int(w * 0.72))
    ox        = (w - pill_w) // 2
    r_pill    = (h - 6) // 2
    inner_margin = r_pill + 8
    inner_w   = pill_w - inner_margin * 2
    inner_mid = h // 2
    max_h     = r_pill - 4
    nb        = len(vu_bar_rects)   # nombre réel créé (adaptatif)
    gap       = max(2, (inner_w - nb * BAR_WIDTH) // max(1, nb - 1))
    total_bars_w = nb * BAR_WIDTH + (nb - 1) * gap
    start_x   = ox + (pill_w - total_bars_w) // 2
    level   = vu_level[0]
    offset  = wave_offset[0]

    # Couleur : cyan en base, orange si fort, rouge si saturé
    t = theme()
    if level > 0.75:
        color = COLOR_RED
    elif level > 0.45:
        color = COLOR_ORANGE
    else:
        color = t.get("vu_color", "#22d3ee")

    for i in range(nb):
        x1 = start_x + i * (BAR_WIDTH + gap)
        x2 = x1 + BAR_WIDTH
        profile = BELL_PROFILE[i % NB_BARRES]   # profil bell adaptatif
        wave  = 0.7 + 0.3 * fast_sin(offset + i * 0.5)
        idle  = profile * (2 + 1.5 * abs(fast_sin(offset * 0.5 + i * 0.4)))
        active = profile * level * max_h * wave * 2.8
        bar_h  = min(max(idle, active), max_h)

        vu_canvas.coords(vu_bar_rects[i],   x1, inner_mid - bar_h + BAR_RADIUS,     x2, inner_mid + bar_h - BAR_RADIUS)
        vu_canvas.coords(vu_bar_tops[i],    x1, inner_mid - bar_h,                  x2, inner_mid - bar_h + BAR_RADIUS * 2)
        vu_canvas.coords(vu_bar_bottoms[i], x1, inner_mid + bar_h - BAR_RADIUS * 2, x2, inner_mid + bar_h)

    if color != _vu_last_color[0]:
        for i in range(nb):
            vu_canvas.itemconfig(f"bar_{i}", fill=color)
        _vu_last_color[0] = color

def on_vu_configure(e):
    """Met à jour la largeur du VU-mètre."""
    if e.width > 10:
        vu_width[0] = e.width
        if vu_objects_created[0]:
            vu_objects_created[0] = False
            vu_bg_objects.clear()
            vu_bar_rects.clear()
            vu_bar_tops.clear()
            vu_bar_bottoms.clear()
            vu_canvas.delete("all")
            _vu_last_color[0] = None

vu_canvas.bind("<Configure>", on_vu_configure)

def update_vu():
    """Boucle d'animation du VU-mètre."""
    if _app_closing[0]:
        return
    
    try:
        # Ne pas dessiner si fenêtre minimisée
        if root.state() == "iconic" or not root.winfo_viewable():
            if not _app_closing[0]:
                root.after(100, update_vu)
            return
        
        wave_offset[0] += WAVE_SPEED
        vu_level[0] *= VU_DECAY
        update_vu_objects()
    except Exception:
        pass
    
    if not _app_closing[0]:
        root.after(VU_REFRESH_MS, update_vu)

root.after(200, update_vu)

# ── Zone texte — police compacte (style original) ────────────────────────
texte_label = tk.Label(root, text="", fg=theme()["fg"], bg=theme()["bg"],
                       font=("Consolas", 10), wraplength=saved_w - 40,
                       justify="left", height=2, anchor="w")
texte_label.pack(fill="x", padx=10, pady=(4, 0))

_wraplength_job = [None]

def update_wraplength(event=None):
    """Ajuste le wraplength dynamiquement (debounce 100ms)."""
    if _wraplength_job[0]:
        root.after_cancel(_wraplength_job[0])
    def _apply():
        new_width = root.winfo_width() - 40
        texte_label.config(wraplength=max(200, new_width))
        _wraplength_job[0] = None
    _wraplength_job[0] = root.after(100, _apply)

root.bind("<Configure>", lambda e: (schedule_rounded(e), update_wraplength(e)))

# ── Footer — style v2 : liens gauche + bouton pill cyan droite ───────────
VERSION = "v1.4b"

donation_frame = tk.Frame(root, bg=theme()["bg"])
donation_frame.pack(fill="x", side="bottom", padx=14, pady=(0, 10))

# Séparateur fin
sep_line = tk.Frame(donation_frame, height=1, bg=theme()["fg2"])
sep_line.pack(fill="x", pady=(0, 6))

bottom_container = tk.Frame(donation_frame, bg=theme()["bg"])
bottom_container.pack(fill="x")

# ── Liens gauche ─────────────────────────────────────────────────────────
frame_links = tk.Frame(bottom_container, bg=theme()["bg"])
frame_links.pack(side="left")

def open_donation(e):
    """Ouvre le lien PayPal."""
    webbrowser.open(PAYPAL_URL)

donation_label = tk.Label(frame_links, text=tr("support"),
                          fg=theme()["link"], bg=theme()["bg"],
                          font=("Segoe UI", 8), cursor="hand2")
donation_label.pack(side="left")
donation_label.bind("<Button-1>", open_donation)
donation_label._is_clickable = True

def _don_enter(e):
    donation_label.config(fg=COLOR_BLUE)
def _don_leave(e):
    donation_label.config(fg=theme()["link"])
donation_label.bind("<Enter>", _don_enter)
donation_label.bind("<Leave>", _don_leave)

version_label = tk.Label(frame_links, text=f"  •  {VERSION}  •  2026",
                         fg=theme()["fg2"], bg=theme()["bg"],
                         font=("Segoe UI", 8))
version_label.pack(side="left")
separator_label = version_label  # alias pour apply_theme

# Lien site web
SITE_URL = "https://helioman.fr"

site_label = tk.Label(frame_links, text="  •  helioman.fr",
                      fg=theme()["link"], bg=theme()["bg"],
                      font=("Segoe UI", 8), cursor="hand2")
site_label.pack(side="left")
site_label.bind("<Button-1>", lambda e: webbrowser.open(SITE_URL))
site_label._is_clickable = True

def _site_enter(e): site_label.config(fg=COLOR_BLUE)
def _site_leave(e): site_label.config(fg=theme()["link"])
site_label.bind("<Enter>", _site_enter)
site_label.bind("<Leave>", _site_leave)

# Bouton Macros supprimé du footer — accessible via le bouton 🎙 dans le header
btn_macros     = None   # placeholder — plus de bouton footer
btn_macros_bg  = None
btn_macros_txt = None

# ── Thème ─────────────────────────────────────────────────────────────────
def apply_theme():
    """Applique le thème à tous les widgets."""
    t = theme()
    bg = t["bg"]
    root.configure(bg=bg)

    # Header
    frame_top.configure(bg=bg)
    frame_left.configure(bg=bg)
    frame_center.configure(bg=bg)
    frame_right.configure(bg=bg)
    voyant.configure(bg=bg)
    title_label.configure(bg=bg, fg=t.get("fg_title", COLOR_WHITE))
    statut_label.configure(bg=bg, fg=t["fg2"])
    hw_label.configure(bg=bg, fg=t["fg2"])
    try: frame_statut.configure(bg=bg)
    except Exception: pass

    # Boutons header
    btn_icon_bg = t.get("btn_icon_bg", "#2a2a3e")
    btn_fermer.configure(bg=bg)
    btn_fermer.itemconfig(btn_fermer_bg,  fill=btn_icon_bg)
    btn_fermer.itemconfig(btn_fermer_txt, fill=t["btn_fg"])
    btn_settings.configure(bg=bg)
    btn_settings.itemconfig(btn_settings_bg,  fill=btn_icon_bg)
    _redraw_gear(t["btn_fg"])   # btn_settings_txt=None (remplacé par gear canvas items)

    # VU-mètre
    vu_canvas.configure(bg=bg)
    # Recréer les objets au prochain frame pour appliquer la nouvelle couleur
    vu_objects_created[0] = False
    vu_bg_objects.clear(); vu_bar_rects.clear()
    vu_bar_tops.clear();   vu_bar_bottoms.clear()
    vu_canvas.delete("all"); _vu_last_color[0] = None

    # Zone texte
    texte_label.configure(bg=bg, fg=t["fg"])

    # Footer
    donation_frame.configure(bg=bg)
    sep_line.configure(bg=t["fg2"])
    bottom_container.configure(bg=bg)
    frame_links.configure(bg=bg)
    donation_label.configure(bg=bg, fg=t["link"])
    version_label.configure(bg=bg, fg=t["fg2"])
    site_label.configure(bg=bg, fg=t["link"])
    # btn_libre (micro→macros) : fond icon_bg
    btn_libre.configure(bg=bg)
    btn_libre.itemconfig(btn_libre_bg,  fill=t.get("btn_icon_bg","#2a2a3e"))
    btn_libre.itemconfig(btn_libre_txt, fill=COLOR_WHITE)
    # btn_reunion (mode réunion) : vert ou rouge selon état
    btn_reunion.configure(bg=bg)
    btn_reunion.itemconfig(btn_reunion_bg, fill=COLOR_RED if mode_libre[0] else COLOR_GREEN)
    # btn_minimize
    btn_minimize.configure(bg=bg)
    btn_minimize.itemconfig(btn_minimize_bg,  fill=t.get("btn_icon_bg","#2a2a3e"))
    btn_minimize.itemconfig(btn_minimize_txt, fill=t["btn_fg"])

    root.update_idletasks()

# ── Fonctions UI thread-safe ──────────────────────────────────────────────
def set_statut(texte, couleur, voyant_couleur):
    """Met à jour le statut (appeler depuis le thread principal)."""
    statut_label.config(text=texte, fg=couleur)
    voyant.itemconfig(cercle, fill=voyant_couleur)

def set_texte(texte):
    """Met à jour le texte de transcription."""
    texte_label.config(text=texte)

def set_statut_safe(texte, couleur, voyant_couleur):
    """Met à jour le statut de manière thread-safe."""
    if not _app_closing[0]:
        root.after(0, lambda: set_statut(texte, couleur, voyant_couleur))

def set_texte_safe(texte):
    """Met à jour le texte de manière thread-safe."""
    if not _app_closing[0]:
        root.after(0, lambda: set_texte(texte))

# ── Fenêtre Paramètres ────────────────────────────────────────────────────
def open_settings():
    """Ouvre la fenêtre des paramètres."""
    # Empêcher l'ouverture multiple
    if _settings_window[0] is not None:
        try:
            if _settings_window[0].winfo_exists():
                _settings_window[0].lift()
                _settings_window[0].focus_force()
                return
        except Exception:
            pass
    
    t = theme()
    win = tk.Toplevel(root)
    _settings_window[0] = win
    win.title(tr("settings") + " - Whisper Hélio")
    win.configure(bg=t["bg"])
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.93)
    win.overrideredirect(True)
    win.resizable(False, False)

    # Gestion fermeture fenêtre
    def on_close():
        _settings_window[0] = None
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", on_close)

    # ── Barre de titre custom (drag + bouton ✕) ──────────────────────────────
    _title_bar = tk.Frame(win, bg=t.get("header_bg", t["bg"]), height=32)
    _title_bar.pack(fill="x", padx=0, pady=0)
    _title_bar.pack_propagate(False)
    tk.Label(_title_bar, text=tr("settings") + " — Whisper Hélio",
             bg=t.get("header_bg", t["bg"]), fg=t["fg"],
             font=("Consolas", 9, "bold")).pack(side="left", padx=12)

    # Bouton ✕ fermeture
    _btn_cls = tk.Canvas(_title_bar, width=22, height=22,
                         bg=t.get("header_bg", t["bg"]), highlightthickness=0, cursor="hand2")
    _btn_cls.pack(side="right", padx=(0, 6), pady=5)
    _cls_bg  = _btn_cls.create_oval(1, 1, 21, 21, fill=t.get("btn_icon_bg", "#2a2a3e"), outline="")
    _cls_txt = _btn_cls.create_text(11, 11, text="✕", fill=t["btn_fg"], font=("Segoe UI", 8, "bold"))
    def _cls_enter(e): _btn_cls.itemconfig(_cls_bg, fill=COLOR_RED_DARK); _btn_cls.itemconfig(_cls_txt, fill=COLOR_WHITE)
    def _cls_leave(e): _btn_cls.itemconfig(_cls_bg, fill=t.get("btn_icon_bg","#2a2a3e")); _btn_cls.itemconfig(_cls_txt, fill=t["btn_fg"])
    _btn_cls.bind("<Enter>",    _cls_enter)
    _btn_cls.bind("<Leave>",    _cls_leave)
    _btn_cls.bind("<Button-1>", lambda e: on_close())

    # Drag sur la barre de titre
    _drag = {"x": 0, "y": 0}
    def _drag_start(e): _drag["x"] = e.x_root - win.winfo_x(); _drag["y"] = e.y_root - win.winfo_y()
    def _drag_move(e):  win.geometry(f"+{e.x_root - _drag['x']}+{e.y_root - _drag['y']}")
    _title_bar.bind("<ButtonPress-1>", _drag_start)
    _title_bar.bind("<B1-Motion>",     _drag_move)
    for _lbl in _title_bar.winfo_children():
        if isinstance(_lbl, tk.Label):
            _lbl.bind("<ButtonPress-1>", _drag_start)
            _lbl.bind("<B1-Motion>",     _drag_move)

    # Séparateur sous la barre de titre
    tk.Frame(win, bg=t.get("sep", "#3a3a52"), height=1).pack(fill="x")

    # Contenu
    tk.Label(win, text=tr("hardware", hw=hw_info), bg=t["bg"], fg=COLOR_PURPLE,
             font=("Consolas", 9)).pack(pady=(14, 10))

    frame = tk.Frame(win, bg=t["bg"])
    frame.pack(fill="x", padx=30, pady=5)

    v_theme = tk.StringVar(win, value=config["theme"])
    v_model = tk.StringVar(win, value=config["model"])
    v_device = tk.StringVar(win, value=config["device"])
    v_lang = tk.StringVar(win, value=config["language"])
    v_hotkey = tk.StringVar(win, value=config["hotkey"])
    v_position = tk.StringVar(win, value=config["position"])
    v_ui_lang = tk.StringVar(win, value=config["ui_lang"])

    labels = [
        (tr("theme"), v_theme, VALID_THEMES),
        (tr("model"), v_model, VALID_MODELS),
        (tr("device"), v_device, VALID_DEVICES),
        (tr("lang"), v_lang, VALID_LANGUAGES),
        (tr("shortcut"), v_hotkey, VALID_HOTKEYS),
        (tr("position"), v_position, VALID_POSITIONS),
        (tr("ui_lang"), v_ui_lang, VALID_UI_LANGS),
    ]
    
    for label_text, var, options in labels:
        f = tk.Frame(frame, bg=t["bg"])
        f.pack(fill="x", pady=6)
        tk.Label(f, text=label_text, bg=t["bg"], fg=t["fg2"],
                 font=("Consolas", 10), width=18, anchor="w").pack(side="left")
        menu = tk.OptionMenu(f, var, *options)
        menu.config(bg="#2d2d44", fg="white", font=("Consolas", 9),
                   activebackground="#3d3d54", activeforeground="white",
                   highlightthickness=0, width=22)
        menu["menu"].config(bg="#2d2d44", fg="white", font=("Consolas", 9))
        menu.pack(side="left", padx=8)

    tk.Label(win, text=tr("restart_note"), bg=t["bg"], fg=COLOR_RED,
             font=("Consolas", 9)).pack(pady=(15, 8))

    _settings_vars = {
        "theme": v_theme, "model": v_model, "device": v_device,
        "language": v_lang, "hotkey": v_hotkey, "position": v_position,
        "ui_lang": v_ui_lang,
    }

    def save_and_close():
        for key, var in _settings_vars.items():
            config[key] = var.get()
        _current_theme[0] = None  # Reset cache thème
        _tr_cache.clear()           # Reset cache traductions
        save_config(config)
        apply_theme()
        title_label.config(text=tr("title"))
        donation_label.config(text=tr("support"))
        hotkey_changed[0] = True
        set_statut(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)
        _settings_window[0] = None
        win.destroy()

    # ── Bouton 💾 SAUVEGARDER — rectangle arrondi bleu ──────────────────────
    _sf = tk.Frame(win, bg=t["bg"])
    _sf.pack(pady=(8, 20))
    _SW, _SH2 = 170, 36
    _btn_sv = tk.Canvas(_sf, width=_SW, height=_SH2, bg=t["bg"], highlightthickness=0, cursor="hand2")
    _btn_sv.pack()
    _sv_c  = "#2563eb"
    _sv_ho = "#1d4ed8"
    # Fond rectangle arrondi : oval gauche + oval droite + rect centre (tag "bg_sv")
    _btn_sv.create_oval(2, 2, _SH2-2, _SH2-2,             fill=_sv_c, outline="", tags="bg_sv")
    _btn_sv.create_oval(_SW-_SH2+2, 2, _SW-2, _SH2-2,     fill=_sv_c, outline="", tags="bg_sv")
    _btn_sv.create_rectangle(_SH2//2, 2, _SW-_SH2//2, _SH2-2, fill=_sv_c, outline="", tags="bg_sv")
    # Icône centrée dans l'arrondi gauche
    _btn_sv.create_text(_SH2//2, _SH2//2, text="💾", font=("Segoe UI", 12), fill="white", tags="ico_sv")
    # Texte avec espace suffisant après l'icône
    _btn_sv.create_text(_SH2 + (_SW - _SH2)//2, _SH2//2, text="SAUVEGARDER",
                        fill="white", font=("Segoe UI", 9, "bold"), tags="txt_sv")
    def _sv_enter(e): _btn_sv.itemconfig("bg_sv", fill=_sv_ho)
    def _sv_leave(e): _btn_sv.itemconfig("bg_sv", fill=_sv_c)
    _btn_sv.bind("<Enter>", _sv_enter)
    _btn_sv.bind("<Leave>", _sv_leave)
    _btn_sv.bind("<Button-1>", lambda e: save_and_close())

    # Taille et centrage
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"520x600+{(sw - 520) // 2}+{(sh - 600) // 2}")
    win.minsize(520, 580)
    win.after(100, lambda: _apply_rounded_toplevel(win))
    win.bind("<Configure>", lambda e: win.after(80, lambda: _apply_rounded_toplevel(win)))

btn_settings.bind("<Button-1>", lambda e: open_settings())

# ── Fenêtre Macros ────────────────────────────────────────────────────────
def process_and_paste(texte, delay=0):
    """Applique macros + actions + dictionnaire puis colle. Retourne le texte final."""
    texte = apply_macros(texte)
    texte = apply_actions(texte)
    texte = apply_dictionary(texte)
    if texte:
        set_texte_safe(texte)
        copy_and_paste(texte, delay=delay)
    return texte

def _build_macros_cache():
    """Compile les patterns regex des macros — le NOM est le déclencheur direct."""
    macros = config.get("macros", [])
    if not macros:
        _regex_cache["macros"] = []
        return
    entries = []
    for macro in macros:
        name = macro.get("name", "").strip()
        repl = macro.get("text", "")
        if not name:
            continue
        # Le nom peut contenir des espaces ou underscores → on normalise
        name_pattern = re.escape(name.replace("_", " "))
        pat = re.compile(r'\b' + name_pattern + r'\b', re.IGNORECASE)
        entries.append((pat, repl.replace("\\", "\\\\")))
    _regex_cache["macros"] = entries

def apply_macros(text):
    """Remplace les macros vocales dans le texte transcrit."""
    if not text:
        return text
    if _regex_cache["macros"] is None:
        _build_macros_cache()
    entries = _regex_cache["macros"]
    if not entries:
        return text
    result = text
    for pat, repl in entries:
        result = pat.sub(repl, result)
    return result

# ── Actions vocales prédéfinies ───────────────────────────────────────────
_office_cache = {}

def _find_office(app_name):
    """Cherche Excel ou Word dans les emplacements Office standard (résultat mis en cache)."""
    key = app_name.upper()
    if key in _office_cache:
        return _office_cache[key]
    candidates = [
        rf"C:\Program Files\Microsoft Office\root\Office16\{app_name}",
        rf"C:\Program Files\Microsoft Office\root\Office15\{app_name}",
        rf"C:\Program Files (x86)\Microsoft Office\root\Office16\{app_name}",
        rf"C:\Program Files (x86)\Microsoft Office\Office16\{app_name}",
        rf"C:\Program Files (x86)\Microsoft Office\Office15\{app_name}",
        rf"C:\Program Files\Microsoft Office\Office16\{app_name}",
    ]
    result = next((p for p in candidates if os.path.exists(p)), None)
    _office_cache[key] = result
    return result

_browser_cache = {}

def _find_browser(exe_name, *extra_paths):
    """Cherche un navigateur dans les emplacements standards (résultat mis en cache)."""
    key = exe_name.lower()
    if key in _browser_cache:
        return _browser_cache[key]
    candidates = [
        rf"C:\Program Files\{extra_paths[0] if extra_paths else ''}\{exe_name}",
        rf"C:\Program Files (x86)\{extra_paths[0] if extra_paths else ''}\{exe_name}",
    ] if extra_paths else []
    candidates += [rf"C:\Program Files\{exe_name}", rf"C:\Program Files (x86)\{exe_name}"]
    result = next((p for p in candidates if os.path.exists(p)), exe_name)
    _browser_cache[key] = result
    return result

# Actions intégrées : { nom_vocal: (chemin_ou_commande, label_affichage) }
BUILTIN_ACTIONS = {
    "explorateur":  ("explorer.exe",    "Explorateur Windows"),
    "explorer":     ("explorer.exe",    "Explorateur Windows"),
    "bureau":       (["explorer.exe", "shell:Desktop"], "Bureau"),
    "calculatrice": ("calc.exe",        "Calculatrice"),
    "bloc-notes":   ("notepad.exe",     "Bloc-notes"),
    "notepad":      ("notepad.exe",     "Bloc-notes"),
    "taches":       ("taskmgr.exe",     "Gestionnaire de taches"),
    "paint":        ("mspaint.exe",     "Paint"),
    "excel":        (None,              "Excel"),   # chemin résolu dynamiquement
    "word":         (None,              "Word"),    # chemin résolu dynamiquement
    "chrome":       (None,              "Chrome"),
    "firefox":      (None,              "Firefox"),
    "edge":         ("msedge.exe",      "Microsoft Edge"),
}

def _resolve_builtin(name):
    """Résout le chemin réel d'une action intégrée."""
    entry = BUILTIN_ACTIONS.get(name.lower())
    if not entry:
        return None, None
    cmd, label = entry
    if cmd is not None:
        return cmd, label
    # Résolution dynamique pour les programmes dont le chemin varie
    n = name.lower()
    if n == "excel":
        path = _find_office("EXCEL.EXE")
        return path or "excel.exe", label   # fallback via PATH
    if n == "word":
        path = _find_office("WINWORD.EXE")
        return path or "winword.exe", label  # fallback via PATH
    if n == "chrome":
        path = _find_browser("chrome.exe", "Google\\Chrome\\Application")
        return path, label   # _find_browser retourne exe_name si introuvable
    if n == "firefox":
        path = _find_browser("firefox.exe", "Mozilla Firefox")
        return path, label
    return None, label

def _build_actions_cache():
    """Compile les patterns regex des actions (mis en cache)."""
    trigger = config.get("action_trigger", "action").lower().strip()
    if not trigger:
        _regex_cache["actions"] = []
        return
    all_actions = {}
    for name in BUILTIN_ACTIONS:
        all_actions[name] = ("builtin", name)
    for act in config.get("actions", []):
        name = act.get("name", "").lower().strip()
        path = act.get("path", "").strip()
        if name and path:
            all_actions[name] = ("custom", path)
    entries = []
    for name, (kind, value) in all_actions.items():
        pat = re.compile(r'\b' + re.escape(trigger) + r'\s+' + re.escape(name) + r'\b', re.IGNORECASE)
        entries.append((pat, name, kind, value))
    _regex_cache["actions"] = entries

def apply_actions(text):
    """Détecte et exécute les actions vocales. Retourne le texte nettoyé."""
    if not text:
        return text
    if _regex_cache["actions"] is None:
        _build_actions_cache()
    entries = _regex_cache["actions"]
    if not entries:
        return text

    result = text
    for pat, name, kind, value in entries:
        if not pat.search(result):
            continue
        launched     = False
        display_name = name  # valeur par défaut
        try:
            if kind == "builtin":
                cmd, label = _resolve_builtin(name)
                display_name = label or name
                if cmd:
                    subprocess.Popen(cmd if isinstance(cmd, list) else [cmd])
                    launched = True
                else:
                    set_statut_safe(tr("action_not_found", name=display_name), COLOR_ORANGE, COLOR_ORANGE)
            else:  # custom
                # Sécurité : accepter uniquement les .exe locaux (pas de .bat/.cmd/.vbs/UNC)
                _val_lower = value.lower()
                _is_safe = (
                    _val_lower.endswith('.exe')
                    and not value.startswith('\\\\')     # bloquer UNC \\serveur\...
                    and os.path.isabs(value)              # chemin absolu obligatoire
                    and os.path.exists(value)
                )
                if _is_safe:
                    subprocess.Popen([value])
                    launched = True
                else:
                    set_statut_safe(tr("action_not_found", name=display_name), COLOR_ORANGE, COLOR_ORANGE)
            if launched:
                set_statut_safe(tr("action_launched", name=display_name), COLOR_GREEN, COLOR_GREEN)
        except Exception as e:
            log_error(e)
        result = pat.sub("", result).strip()
    return result

def _build_dictionary_cache():
    """Compile les patterns regex du dictionnaire (mis en cache)."""
    dictionary = config.get("dictionary", [])
    if not dictionary:
        _regex_cache["dictionary"] = []
        return
    entries = []
    for entry in dictionary:
        wrong   = entry.get("wrong", "").strip()
        correct = entry.get("correct", "")
        if not wrong:
            continue
        pat = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)
        entries.append((pat, correct.replace("\\", "\\\\")))
    _regex_cache["dictionary"] = entries

def apply_dictionary(text):
    """Corrige les mots mal transcrits par Whisper via le dictionnaire utilisateur."""
    if not text:
        return text
    if _regex_cache["dictionary"] is None:
        _build_dictionary_cache()
    entries = _regex_cache["dictionary"]
    if not entries:
        return text
    result = text
    for pat, repl in entries:
        result = pat.sub(repl, result)
    return result

def _make_scroll_area(parent, bg):
    """Crée une zone scrollable (Canvas + Scrollbar + Frame intérieur).
    Retourne (canvas, inner_frame) — factorisation des 3 onglets identiques."""
    fs = tk.Frame(parent, bg=bg)
    fs.pack(fill="both", expand=True, padx=16, pady=4)
    cs = tk.Canvas(fs, bg=bg, highlightthickness=0)
    sb = tk.Scrollbar(fs, orient="vertical", command=cs.yview)
    cs.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    cs.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(cs, bg=bg)
    cw = cs.create_window((0, 0), window=inner, anchor="nw")

    def _cfg(e):
        cs.configure(scrollregion=cs.bbox("all"))
        cs.itemconfig(cw, width=cs.winfo_width())
    inner.bind("<Configure>", _cfg)
    cs.bind("<Configure>", lambda e: cs.itemconfig(cw, width=e.width))

    def _mw(e): cs.yview_scroll(int(-1 * (e.delta / 120)), "units")
    cs.bind("<MouseWheel>", _mw)
    inner.bind("<MouseWheel>", _mw)

    return cs, inner, _mw

def _apply_rounded_toplevel(win):
    """Applique les coins arrondis à une fenêtre Toplevel."""
    try:
        HWND = ctypes.windll.user32.GetParent(win.winfo_id())
        w, h = win.winfo_width(), win.winfo_height()
        if w > 10 and h > 10:
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w+1, h+1, 28, 28)
            ctypes.windll.user32.SetWindowRgn(HWND, hrgn, True)
    except Exception:
        pass

def open_macros():
    """Ouvre le gestionnaire de macros et actions vocales (3 onglets)."""
    if _macros_window[0] is not None:
        try:
            if _macros_window[0].winfo_exists():
                _macros_window[0].lift()
                _macros_window[0].focus_force()
                return
        except Exception:
            pass

    t   = theme()
    bg  = t["bg"]
    fg  = t["fg"]
    fg2 = t["fg2"]
    vc  = t.get("vu_color", "#22d3ee")
    accent = t.get("btn_icon_bg", "#2a2a3e")

    win = tk.Toplevel(root)
    _macros_window[0] = win
    win.title(tr("macro_title") + " - Whisper Hélio")
    win.configure(bg=bg)
    win.attributes("-topmost", True)
    win.resizable(True, True)
    win.overrideredirect(True)

    def on_close_macros():
        _macros_window[0] = None
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", on_close_macros)

    # ── Header personnalisé (drag + titre + ✕) ────────────────────────────
    frame_hdr = tk.Frame(win, bg=bg)
    frame_hdr.pack(fill="x", padx=14, pady=(12, 0))

    tk.Label(frame_hdr, text=tr("macro_title"), bg=bg,
             fg=t.get("fg_title", fg), font=("Segoe UI", 11, "bold")).pack(side="left", expand=True)

    # Bouton ✕
    btn_cls = tk.Canvas(frame_hdr, width=22, height=22, bg=bg, highlightthickness=0, cursor="hand2")
    btn_cls.pack(side="right")
    _bc_bg  = btn_cls.create_oval(1, 1, 21, 21, fill=accent, outline="")
    _bc_txt = btn_cls.create_text(11, 11, text="✕", fill=fg2, font=("Segoe UI", 8, "bold"))

    def _bc_enter(e): btn_cls.itemconfig(_bc_bg, fill=COLOR_RED_DARK); btn_cls.itemconfig(_bc_txt, fill="white")
    def _bc_leave(e): btn_cls.itemconfig(_bc_bg, fill=accent);         btn_cls.itemconfig(_bc_txt, fill=fg2)
    btn_cls.bind("<Button-1>", lambda e: on_close_macros())
    btn_cls.bind("<Enter>", _bc_enter)
    btn_cls.bind("<Leave>", _bc_leave)

    # Drag sur le header
    _hdrag = {"x": 0, "y": 0}
    def _hdr_press(e):  _hdrag["x"] = e.x_root - win.winfo_x(); _hdrag["y"] = e.y_root - win.winfo_y()
    def _hdr_drag(e):   win.geometry(f"+{e.x_root - _hdrag['x']}+{e.y_root - _hdrag['y']}")
    for _hw in (frame_hdr, frame_hdr.winfo_children()[0] if frame_hdr.winfo_children() else frame_hdr):
        try:
            _hw.bind("<ButtonPress-1>", _hdr_press)
            _hw.bind("<B1-Motion>",     _hdr_drag)
        except Exception:
            pass

    # Séparateur cyan (accent) sous la barre de titre
    tk.Frame(win, height=1, bg=t.get("vu_color", "#22d3ee")).pack(fill="x", padx=14, pady=(8, 0))

    # ── Notebook (onglets) ─────────────────────────────────────────────────
    style = ttk.Style(win)
    style.theme_use("default")
    style.configure("Helio.TNotebook",     background=bg, borderwidth=0)
    style.configure("Helio.TNotebook.Tab",
                    background=accent, foreground=fg2,
                    font=("Segoe UI", 9, "bold"),
                    padding=[14, 7])
    style.map("Helio.TNotebook.Tab",
              background=[("selected", vc)],
              foreground=[("selected", bg)])

    # ── Footer fixe (AVANT notebook dans le pack pour être toujours visible) ─
    # On le place ici mais avec side="bottom" → il sera rendu en dernier
    # mais réservé en premier dans l'espace disponible
    footer_frame = tk.Frame(win, bg=bg)
    footer_frame.pack(side="bottom", fill="x", padx=14, pady=(4, 14))

    tk.Frame(footer_frame, height=1, bg=fg2).pack(fill="x", pady=(0, 8))

    _MSW, _MSH = 170, 36
    _btn_save = tk.Canvas(footer_frame, width=_MSW, height=_MSH, bg=bg, highlightthickness=0, cursor="hand2")
    _btn_save.pack()
    _bs_c  = "#2563eb"
    _bs_ho = COLOR_RED
    _btn_save.create_oval(2, 2, _MSH-2, _MSH-2,               fill=_bs_c, outline="", tags="bg_bs")
    _btn_save.create_oval(_MSW-_MSH+2, 2, _MSW-2, _MSH-2,     fill=_bs_c, outline="", tags="bg_bs")
    _btn_save.create_rectangle(_MSH//2, 2, _MSW-_MSH//2, _MSH-2, fill=_bs_c, outline="", tags="bg_bs")
    _btn_save.create_text(_MSH//2, _MSH//2, text="💾", font=("Segoe UI", 11), fill="white")
    _btn_save.create_text(_MSH + (_MSW-_MSH)//2, _MSH//2, text="SAUVEGARDER",
                           fill="white", font=("Segoe UI", 9, "bold"))
    def _bs_enter(e): _btn_save.itemconfig("bg_bs", fill=_bs_ho)
    def _bs_leave(e): _btn_save.itemconfig("bg_bs", fill=_bs_c)
    _btn_save.bind("<Enter>", _bs_enter)
    _btn_save.bind("<Leave>", _bs_leave)
    # bind save_all défini plus bas — on le connecte après

    notebook = ttk.Notebook(win, style="Helio.TNotebook")
    notebook.pack(fill="both", expand=True, padx=12, pady=(8, 0))

    # ═══════════════════════════════════════════════════════════════════════
    # ONGLET 1 — MACROS TEXTE
    # ═══════════════════════════════════════════════════════════════════════
    tab_macros = tk.Frame(notebook, bg=bg)
    notebook.add(tab_macros, text=f"  {tr('macros_tab')}  ")

    # v_trigger maintenu pour compatibilité save_all (valeur interne non affichée)
    v_trigger = tk.StringVar(win, value="")

    # Aide macros — explication claire du fonctionnement
    tk.Label(tab_macros,
             text="Dites le nom de la macro → Whisper le remplace par le texte.",
             bg=bg, fg=COLOR_BLUE,
             font=("Consolas", 8), wraplength=430).pack(pady=(8, 4))

    # En-têtes colonnes macros
    fh_m = tk.Frame(tab_macros, bg=bg)
    fh_m.pack(fill="x", padx=16)
    tk.Label(fh_m, text="Nom déclencheur", bg=bg, fg=fg2,
             font=("Consolas", 8, "bold"), width=15, anchor="w").pack(side="left")
    tk.Label(fh_m, text="Texte à coller", bg=bg, fg=fg2,
             font=("Consolas", 8, "bold"), anchor="w").pack(side="left", padx=(6, 0))

    # Bouton + Ajouter AVANT la scroll area (sinon écrasé par expand=True)
    _btn_add_m = tk.Canvas(tab_macros, width=150, height=32, bg=bg, highlightthickness=0, cursor="hand2")
    _btn_add_m.pack(pady=(6, 4))
    _btn_add_m.create_oval(2, 2, 32-2, 32-2,          fill=vc, outline="", tags="bg_btn_add_m")
    _btn_add_m.create_oval(150-32+2, 2, 150-2, 32-2,  fill=vc, outline="", tags="bg_btn_add_m")
    _btn_add_m.create_rectangle(32//2, 2, 150-32//2, 32-2, fill=vc, outline="", tags="bg_btn_add_m")
    _btn_add_m.create_text(32//2, 32//2, text="+", font=("Segoe UI", 13, "bold"), fill=bg)
    _btn_add_m.create_text(32+(150-32)//2, 32//2, text=tr("macro_add"),
                       fill=bg, font=("Segoe UI", 9, "bold"))
    def _btn_add_m_enter(e): _btn_add_m.itemconfig("bg_btn_add_m", fill=COLOR_RED)
    def _btn_add_m_leave(e): _btn_add_m.itemconfig("bg_btn_add_m", fill=vc)
    _btn_add_m.bind("<Enter>", _btn_add_m_enter)
    _btn_add_m.bind("<Leave>", _btn_add_m_leave)
    _btn_add_m.bind("<Button-1>", lambda e: on_add_macro())

    # Zone scrollable macros (expand=True → doit être après le bouton)
    cs_m, if_m, _mw_m = _make_scroll_area(tab_macros, bg)

    macro_rows = []

    def add_macro_row(name="", text=""):
        row = tk.Frame(if_m, bg=bg)
        row.pack(fill="x", pady=2)
        vn = tk.StringVar(win, value=name)
        vt = tk.StringVar(win, value=text)
        en = tk.Entry(row, textvariable=vn, width=13,
                      bg="#2d2d44", fg="white", font=("Consolas", 9),
                      insertbackground="white", relief="flat", bd=4)
        en.pack(side="left")
        et = tk.Entry(row, textvariable=vt,
                      bg="#2d2d44", fg="white", font=("Consolas", 9),
                      insertbackground="white", relief="flat", bd=4)
        et.pack(side="left", fill="x", expand=True, padx=(6, 6))

        def del_m():
            try: macro_rows.remove((vn, vt))
            except ValueError: pass
            row.destroy()

        bd = tk.Button(row, text=tr("macro_delete"), command=del_m,
                       bg=COLOR_RED_DARK, fg="white", relief="flat",
                       font=("Consolas", 8), cursor="hand2", padx=5)
        bd.pack(side="left")
        for w in (row, en, et, bd):
            w.bind("<MouseWheel>", _mw_m)
        macro_rows.append((vn, vt))

    for m in config.get("macros", []):
        add_macro_row(m.get("name", ""), m.get("text", ""))

    def on_add_macro():
        add_macro_row()
        win.after(50, lambda: cs_m.yview_moveto(1.0))

    # ═══════════════════════════════════════════════════════════════════════
    # ONGLET 2 — ACTIONS VOCALES
    # ═══════════════════════════════════════════════════════════════════════
    tab_actions = tk.Frame(notebook, bg=bg)
    notebook.add(tab_actions, text=f"  {tr('actions_tab')}  ")

    # Mot déclencheur actions
    frame_trig_a = tk.Frame(tab_actions, bg=bg)
    frame_trig_a.pack(fill="x", padx=16, pady=(10, 2))
    tk.Label(frame_trig_a, text=tr("action_trigger_label") + " :",
             bg=bg, fg=fg2, font=("Consolas", 9)).pack(side="left")
    v_action_trigger = tk.StringVar(win, value=config.get("action_trigger", "action"))
    tk.Entry(frame_trig_a, textvariable=v_action_trigger, width=12,
             bg="#2d2d44", fg="white", font=("Consolas", 9),
             insertbackground="white", relief="flat", bd=4).pack(side="left", padx=6)

    # Aide actions
    tk.Label(tab_actions, text=tr("action_help"), bg=bg, fg=COLOR_BLUE,
             font=("Consolas", 8), wraplength=430).pack(pady=(2, 6))

    # ── Section : Actions intégrées ──────────────────────────────────────
    tk.Label(tab_actions, text=tr("action_builtin"), bg=bg, fg=COLOR_PURPLE,
             font=("Consolas", 9, "bold")).pack(anchor="w", padx=16)

    frame_builtin = tk.Frame(tab_actions, bg="#2d2d44", bd=0)
    frame_builtin.pack(fill="x", padx=16, pady=(4, 10))

    # Grille des actions intégrées (icône + nom)
    BUILTIN_DISPLAY = [
        ("🗂 explorateur",  "Ouvre l'Explorateur Windows"),
        ("💻 bureau",       "Affiche le Bureau"),
        ("📊 excel",        "Lance Microsoft Excel"),
        ("📝 word",         "Lance Microsoft Word"),
        ("🧮 calculatrice", "Ouvre la Calculatrice"),
        ("📓 bloc-notes",   "Ouvre le Bloc-notes"),
        ("🌐 chrome",       "Lance Google Chrome"),
        ("🦊 firefox",      "Lance Firefox"),
        ("🌐 edge",         "Lance Microsoft Edge"),
        ("⚙ taches",       "Gestionnaire des taches"),
        ("🎨 paint",        "Ouvre Paint"),
    ]

    trigger_example = config.get("action_trigger", "action")
    for i, (label, tooltip) in enumerate(BUILTIN_DISPLAY):
        col = i % 3
        row_i = i // 3
        cell = tk.Frame(frame_builtin, bg="#3a3a55", bd=1, relief="solid")
        cell.grid(row=row_i, column=col, padx=3, pady=3, sticky="ew")
        frame_builtin.grid_columnconfigure(col, weight=1)
        # Nom du mot vocal (ex: "explorateur")
        vocal_name = label.split(" ", 1)[1]
        tk.Label(cell, text=label, bg="#3a3a55", fg="white",
                 font=("Consolas", 8, "bold")).pack(anchor="w", padx=6, pady=(4, 0))
        tk.Label(cell, text=f'→ dites: "{trigger_example} {vocal_name}"',
                 bg="#3a3a55", fg=fg2,
                 font=("Consolas", 7)).pack(anchor="w", padx=6, pady=(0, 4))

    # ── Section : Actions personnalisées ─────────────────────────────────
    tk.Label(tab_actions, text=tr("action_custom"), bg=bg, fg=COLOR_GREEN,
             font=("Consolas", 9, "bold")).pack(anchor="w", padx=16, pady=(6, 2))

    # Ligne titre colonnes
    fh_a = tk.Frame(tab_actions, bg=bg)
    fh_a.pack(fill="x", padx=16, pady=(0, 2))
    tk.Label(fh_a, text="Nom vocal", bg=bg, fg=fg2,
             font=("Consolas", 8, "bold"), width=13, anchor="w").pack(side="left")
    tk.Label(fh_a, text="Programme (.exe)", bg=bg, fg=fg2,
             font=("Consolas", 8, "bold"), anchor="w").pack(side="left", padx=(6, 0))

    # Bouton + Ajouter — centré, sur sa propre ligne, style pill cyan
    _W_BTN_A = 180
    _H_BTN_A = 30
    _btn_add_a = tk.Canvas(tab_actions, width=_W_BTN_A, height=_H_BTN_A,
                           bg=bg, highlightthickness=0, cursor="hand2")
    _btn_add_a.pack(pady=(2, 4))
    _r = _H_BTN_A // 2
    _btn_add_a.create_oval(1, 1, _r*2-1, _H_BTN_A-1,                     fill=vc, outline="", tags="bg_btn_add_a")
    _btn_add_a.create_oval(_W_BTN_A-_r*2+1, 1, _W_BTN_A-1, _H_BTN_A-1,  fill=vc, outline="", tags="bg_btn_add_a")
    _btn_add_a.create_rectangle(_r, 1, _W_BTN_A-_r, _H_BTN_A-1,          fill=vc, outline="", tags="bg_btn_add_a")
    _btn_add_a.create_text(_r - 2, _H_BTN_A//2, text="+",
                           font=("Segoe UI", 13, "bold"), fill=bg)
    _btn_add_a.create_text(_r + (_W_BTN_A - _r) // 2 + 2, _H_BTN_A//2,
                           text="Ajouter une action",
                           fill=bg, font=("Segoe UI", 9, "bold"))
    def _btn_add_a_enter(e): _btn_add_a.itemconfig("bg_btn_add_a", fill=COLOR_GREEN)
    def _btn_add_a_leave(e): _btn_add_a.itemconfig("bg_btn_add_a", fill=vc)
    _btn_add_a.bind("<Enter>", _btn_add_a_enter)
    _btn_add_a.bind("<Leave>", _btn_add_a_leave)

    # Zone scrollable actions perso
    _fa_scroll_outer = tk.Frame(tab_actions, bg=bg)
    _fa_scroll_outer.pack(fill="x", expand=False, padx=16, pady=0)
    cs_a = tk.Canvas(_fa_scroll_outer, bg=bg, highlightthickness=0, height=110)
    _fa_sb = tk.Scrollbar(_fa_scroll_outer, orient="vertical", command=cs_a.yview)
    cs_a.configure(yscrollcommand=_fa_sb.set)
    if_a = tk.Frame(cs_a, bg=bg)
    _fa_win = cs_a.create_window((0, 0), window=if_a, anchor="nw")

    def _fa_on_inner_configure(e):
        cs_a.configure(scrollregion=cs_a.bbox("all"))
        # Montrer la scrollbar seulement si contenu dépasse
        if if_a.winfo_reqheight() > cs_a.winfo_height():
            _fa_sb.pack(side="right", fill="y")
        else:
            _fa_sb.pack_forget()

    def _fa_on_canvas_configure(e):
        cs_a.itemconfig(_fa_win, width=e.width)

    if_a.bind("<Configure>", _fa_on_inner_configure)
    cs_a.bind("<Configure>", _fa_on_canvas_configure)
    cs_a.pack(side="left", fill="both", expand=True)

    def _mw_a(e): cs_a.yview_scroll(int(-1*(e.delta/120)), "units")

    action_rows = []

    def add_action_row(name="", path=""):
        row = tk.Frame(if_a, bg=bg)
        row.pack(fill="x", pady=2)
        vn = tk.StringVar(win, value=name)
        vp = tk.StringVar(win, value=path)

        en = tk.Entry(row, textvariable=vn, width=13,
                      bg="#2d2d44", fg="white", font=("Consolas", 9),
                      insertbackground="white", relief="flat", bd=4)
        en.pack(side="left")

        ep = tk.Entry(row, textvariable=vp,
                      bg="#2d2d44", fg="white", font=("Consolas", 9),
                      insertbackground="white", relief="flat", bd=4)
        ep.pack(side="left", fill="x", expand=True, padx=(6, 4))

        def browse():
            f = filedialog.askopenfilename(
                parent=win,
                title="Choisir un programme",
                filetypes=[("Programmes", "*.exe"), ("Tous", "*.*")]
            )
            if f:
                vp.set(f)

        tk.Button(row, text="Parcourir", command=browse,
                  bg=COLOR_BLUE_DARK, fg="white", relief="flat",
                  font=("Consolas", 8), cursor="hand2", padx=5).pack(side="left")

        def del_a():
            try: action_rows.remove((vn, vp))
            except ValueError: pass
            row.destroy()

        tk.Button(row, text="Supprimer", command=del_a,
                  bg=COLOR_RED_DARK, fg="white", relief="flat",
                  font=("Consolas", 8), cursor="hand2", padx=5).pack(side="left", padx=(2, 0))

        for w in (row, en, ep):
            w.bind("<MouseWheel>", _mw_a)
        action_rows.append((vn, vp))

    for a in config.get("actions", []):
        add_action_row(a.get("name", ""), a.get("path", ""))

    def on_add_action():
        add_action_row()
        win.after(50, lambda: cs_a.yview_moveto(1.0))

    _btn_add_a.bind("<Button-1>", lambda e: on_add_action())

    # ═══════════════════════════════════════════════════════════════════════
    # ONGLET 3 — DICTIONNAIRE
    # ═══════════════════════════════════════════════════════════════════════
    tab_dict = tk.Frame(notebook, bg=bg)
    notebook.add(tab_dict, text=f"  {tr('dict_tab')}  ")

    # Aide
    tk.Label(tab_dict, text=tr("dict_help"), bg=bg, fg=COLOR_BLUE,
             font=("Consolas", 8), wraplength=430).pack(pady=(10, 2))
    tk.Label(tab_dict, text=tr("dict_example"), bg=bg, fg=fg2,
             font=("Consolas", 8), wraplength=430).pack(pady=(0, 6))

    # En-têtes colonnes
    fh_d = tk.Frame(tab_dict, bg=bg)
    fh_d.pack(fill="x", padx=16)
    tk.Label(fh_d, text=tr("dict_wrong"), bg=bg, fg=fg2,
             font=("Consolas", 8, "bold"), width=20, anchor="w").pack(side="left")
    tk.Label(fh_d, text="→", bg=bg, fg=COLOR_ORANGE,
             font=("Consolas", 10, "bold")).pack(side="left", padx=(4, 4))
    tk.Label(fh_d, text=tr("dict_correct"), bg=bg, fg=fg2,
             font=("Consolas", 8, "bold"), anchor="w").pack(side="left")

    # Bouton + Ajouter AVANT la scroll area (sinon écrasé par expand=True)
    _vc_color = vc   # capturer la couleur thème avant que vc soit redéfini
    _W_BTN_D = 180
    _H_BTN_D = 32
    _btn_add_d = tk.Canvas(tab_dict, width=_W_BTN_D, height=_H_BTN_D,
                           bg=bg, highlightthickness=0, cursor="hand2")
    _btn_add_d.pack(pady=(6, 4))
    _rd = _H_BTN_D // 2
    _btn_add_d.create_oval(1, 1, _rd*2-1, _H_BTN_D-1,                      fill=_vc_color, outline="", tags="bg_btn_add_d")
    _btn_add_d.create_oval(_W_BTN_D-_rd*2+1, 1, _W_BTN_D-1, _H_BTN_D-1,   fill=_vc_color, outline="", tags="bg_btn_add_d")
    _btn_add_d.create_rectangle(_rd, 1, _W_BTN_D-_rd, _H_BTN_D-1,          fill=_vc_color, outline="", tags="bg_btn_add_d")
    _btn_add_d.create_text(_rd - 2, _H_BTN_D//2, text="+",
                           font=("Segoe UI", 13, "bold"), fill=bg)
    _btn_add_d.create_text(_rd + (_W_BTN_D - _rd) // 2 + 2, _H_BTN_D//2,
                           text="Ajouter un mot",
                           fill=bg, font=("Segoe UI", 9, "bold"))
    def _btn_add_d_enter(e): _btn_add_d.itemconfig("bg_btn_add_d", fill=COLOR_RED)
    def _btn_add_d_leave(e): _btn_add_d.itemconfig("bg_btn_add_d", fill=_vc_color)
    _btn_add_d.bind("<Enter>", _btn_add_d_enter)
    _btn_add_d.bind("<Leave>", _btn_add_d_leave)
    _btn_add_d.bind("<Button-1>", lambda e: on_add_dict())

    # Zone scrollable dictionnaire (expand=True → doit être après le bouton)
    cs_d, if_d, _mw_d = _make_scroll_area(tab_dict, bg)

    dict_rows = []

    def add_dict_row(wrong="", correct=""):
        # Alternance de couleur pour lisibilité (ligne paire / impaire)
        _row_even_bg = "#17172e"
        _row_odd_bg  = "#1f1f38"
        row_bg = _row_even_bg if len(dict_rows) % 2 == 0 else _row_odd_bg

        row = tk.Frame(if_d, bg=row_bg)
        row.pack(fill="x", pady=1)
        vw    = tk.StringVar(win, value=wrong)
        v_cor = tk.StringVar(win, value=correct)  # "vc" réservé à la couleur thème

        ew = tk.Entry(row, textvariable=vw, width=20,
                      bg="#2d2d44", fg="#ff9966", font=("Consolas", 9),
                      insertbackground="white", relief="flat", bd=4)
        ew.pack(side="left", padx=(6, 0), pady=4)

        tk.Label(row, text="→", bg=row_bg, fg=COLOR_ORANGE,
                 font=("Consolas", 10, "bold")).pack(side="left", padx=(4, 4))

        # Bouton supprimer packé en side="right" AVANT ec
        # → ec avec expand=True occupe tout l'espace restant correctement
        def del_d():
            try: dict_rows.remove((vw, v_cor))
            except ValueError: pass
            row.destroy()

        bd = tk.Button(row, text=tr("dict_delete"), command=del_d,
                       bg=COLOR_RED_DARK, fg="white", relief="flat",
                       font=("Consolas", 8), cursor="hand2", padx=5)
        bd.pack(side="right", padx=(0, 6), pady=4)

        ec = tk.Entry(row, textvariable=v_cor,
                      bg="#2d2d44", fg=COLOR_GREEN, font=("Consolas", 9),
                      insertbackground="white", relief="flat", bd=4)
        ec.pack(side="left", fill="x", expand=True, padx=(0, 4), pady=4)

        for w in (row, ew, ec, bd):
            w.bind("<MouseWheel>", _mw_d)
        dict_rows.append((vw, v_cor))

    # Charger le dictionnaire existant
    for d in config.get("dictionary", []):
        add_dict_row(d.get("wrong", ""), d.get("correct", ""))

    def on_add_dict():
        add_dict_row()
        win.after(50, lambda: cs_d.yview_moveto(1.0))

    # ═══════════════════════════════════════════════════════════════════════
    # Bouton Sauvegarder (commun aux deux onglets)
    # ═══════════════════════════════════════════════════════════════════════
    def save_all():
        # Sauvegarder macros texte (le nom est le déclencheur direct)
        config["macros"] = [
            {"name": vn.get().strip(), "text": vt.get()}
            for vn, vt in macro_rows
            if vn.get().strip()
        ]
        # Sauvegarder actions
        config["action_trigger"] = v_action_trigger.get().strip().replace(" ", "") or "action"
        config["actions"] = [
            {"name": vn.get().strip().replace(" ", "_"), "path": vp.get().strip()}
            for vn, vp in action_rows
            if vn.get().strip() and vp.get().strip()
        ]
        # Sauvegarder dictionnaire
        config["dictionary"] = [
            {"wrong": vw.get().strip(), "correct": v_cor.get()}
            for vw, v_cor in dict_rows
            if vw.get().strip()
        ]
        save_config(config)
        _invalidate_regex_cache()   # activer macros/actions/dict immédiatement
        _macros_window[0] = None
        win.destroy()

    # Connecter le bouton save (défini plus haut) à save_all
    _btn_save.bind("<Button-1>", lambda e: save_all())

    # Taille et centrage
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"580x700+{(sw - 580) // 2}+{(sh - 700) // 2}")
    win.minsize(520, 600)
    win.after(100, lambda: _apply_rounded_toplevel(win))
    win.bind("<Configure>", lambda e: win.after(80, lambda: _apply_rounded_toplevel(win)))

# btn_macros remplacé par btn_libre (🎙)

# ── Audio avec Ring Buffer ────────────────────────────────────────────────
class RingBuffer:
    """Buffer circulaire pour l'audio avec thread-safety."""
    
    def __init__(self, max_samples):
        self.buffer = np.zeros(max_samples, dtype=np.float32)
        self.write_pos = 0
        self.length = 0
        self.max_samples = max_samples
        self.lock = threading.Lock()
    
    def append(self, data):
        """Ajoute des données au buffer."""
        data_flat = data.flatten()
        n = len(data_flat)
        
        with self.lock:
            if n >= self.max_samples:
                self.buffer[:] = data_flat[-self.max_samples:]
                self.write_pos = 0
                self.length = self.max_samples
            elif self.write_pos + n <= self.max_samples:
                self.buffer[self.write_pos:self.write_pos + n] = data_flat
                self.write_pos += n
                self.length = min(self.length + n, self.max_samples)
            else:
                first = self.max_samples - self.write_pos
                self.buffer[self.write_pos:] = data_flat[:first]
                self.buffer[:n - first] = data_flat[first:]
                self.write_pos = n - first
                self.length = self.max_samples
    
    def get_data(self):
        """Récupère toutes les données du buffer."""
        with self.lock:
            if self.length == 0:
                return np.array([], dtype=np.float32)
            if self.length < self.max_samples:
                return self.buffer[:self.length].copy()
            # Buffer plein — si write_pos == 0 il est déjà linéaire
            if self.write_pos == 0:
                return self.buffer.copy()
            return np.concatenate([
                self.buffer[self.write_pos:],
                self.buffer[:self.write_pos]
            ])
    
    def clear(self):
        """Vide le buffer."""
        with self.lock:
            self.write_pos = 0
            self.length = 0

# Buffer pour MAX_RECORD_SECONDS
audio_buffer = RingBuffer(SAMPLE_RATE * MAX_RECORD_SECONDS)
is_recording = threading.Event()

def audio_callback(indata, frames, time_info, status):
    """Callback audio avec gestion d'erreur."""
    try:
        if is_recording.is_set():
            audio_buffer.append(indata)
            vu_level[0] = min(1.0, float(np.mean(np.abs(indata))) * 12)
        else:
            vu_level[0] = 0.0
    except Exception as e:
        log_error(e, "Erreur callback audio")

# Initialiser le stream audio
try:
    stream[0] = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32',
                                callback=audio_callback, blocksize=AUDIO_BLOCKSIZE)
    stream[0].start()
except sd.PortAudioError as e:
    log_error(e, "Aucun microphone détecté")
    stream[0] = None

# ── Souris — hook bas niveau WH_MOUSE_LL ─────────────────────────────────
# WH_MOUSE_LL permet de bloquer sélectivement X1/X2 quand ils sont le hotkey.
# RÈGLES Windows :
#   - Pour BLOQUER : retourner 1 sans appeler CallNextHookEx
#   - Pour LAISSER PASSER : appeler CallNextHookEx et retourner sa valeur
# Le hook DOIT être installé depuis le thread principal avec sa message pump
# active → on utilise root.after(0) pour l'installer après mainloop.start().

mouse_x1_pressed = [False]
mouse_x2_pressed = [False]
_mouse_hook_handle = [None]
_mouse_hook_cb     = [None]   # référence OBLIGATOIRE — évite le GC du callback

_WH_MOUSE_LL    = 14
_WM_XBUTTONDOWN = 0x020B
_WM_XBUTTONUP   = 0x020C

_u32.CallNextHookEx.argtypes = [
    ctypes.wintypes.HHOOK,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
_u32.CallNextHookEx.restype  = ctypes.c_ssize_t
_u32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.wintypes.HINSTANCE,
    ctypes.wintypes.DWORD,
]
_u32.SetWindowsHookExW.restype  = ctypes.wintypes.HHOOK

class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt",          ctypes.wintypes.POINT),
        ("mouseData",   ctypes.wintypes.DWORD),
        ("flags",       ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),  # ULONG_PTR : 4 oct Win32, 8 oct Win64
    ]

_HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,          # LRESULT
    ctypes.c_int,              # nCode
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)

def _mouse_ll_proc(nCode, wParam, lParam):
    """Hook bas niveau souris.
    Bloquer = retourner 1 SANS CallNextHookEx.
    Laisser passer = CallNextHookEx + retourner sa valeur.
    """
    if nCode >= 0 and wParam in (_WM_XBUTTONDOWN, _WM_XBUTTONUP):
        try:
            data    = ctypes.cast(lParam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
            xbtn    = (data.mouseData >> 16) & 0xFFFF   # 1 = X1, 2 = X2
            pressed = (wParam == _WM_XBUTTONDOWN)
            hk      = config.get("hotkey", "")
            if xbtn == 1:
                mouse_x1_pressed[0] = pressed
                if hk == "mouse_x1":
                    return 1   # bloquer : X1 est notre hotkey
            elif xbtn == 2:
                mouse_x2_pressed[0] = pressed
                if hk == "mouse_x2":
                    return 1   # bloquer : X2 est notre hotkey
        except Exception:
            pass
    return _u32.CallNextHookEx(_mouse_hook_handle[0], nCode, wParam, lParam)

def _install_mouse_hook():
    """Installe le hook depuis le thread principal avec mainloop actif."""
    _mouse_hook_cb[0]     = _HOOKPROC(_mouse_ll_proc)
    _mouse_hook_handle[0] = _u32.SetWindowsHookExW(
        _WH_MOUSE_LL, _mouse_hook_cb[0], None, 0
    )

def is_hotkey_pressed(hk):
    """Vérifie si le hotkey est pressé."""
    if hk == "mouse_x1":
        return mouse_x1_pressed[0]
    if hk == "mouse_x2":
        return mouse_x2_pressed[0]
    try:
        return keyboard.is_pressed(hk)
    except Exception:
        return False

# ── VAD (Voice Activity Detection) ────────────────────────────────────────
def has_voice(audio_data, threshold=VAD_THRESHOLD):
    """Détecte si l'audio contient de la voix."""
    if len(audio_data) == 0:
        return False
    data = audio_data if audio_data.dtype == np.float32 else audio_data.astype(np.float32)
    rms = np.sqrt(np.mean(data ** 2))
    return bool(np.isfinite(rms) and rms > threshold)

# ── Transcription helper ──────────────────────────────────────────────────
def transcribe_audio(model, audio_data, use_vad=True):
    """Transcrit un tableau numpy en texte."""
    if len(audio_data) < MIN_AUDIO_SAMPLES:
        return ""
    
    # Skip si silence (VAD)
    if use_vad and not has_voice(audio_data):
        return ""
    
    try:
        gc.disable()
        segments, _ = model.transcribe(
            audio_data,
            language=config["language"],
            beam_size=1,
            best_of=1,
            temperature=0,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            vad_filter=True,
        )
        result = " ".join(s.text.strip() for s in segments).strip()
        return result
    except Exception as e:
        log_error(e)
        return ""
    finally:
        gc.enable()   # garanti même sur BaseException

# ── Copie et collage ──────────────────────────────────────────────────────
def fast_copy(text):
    """Copie le texte dans le presse-papier. Retourne True si réussi."""
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        return False

def paste_text():
    """Colle le texte depuis le presse-papier."""
    try:
        keyboard.send("ctrl+v")
    except Exception:
        try:
            pyautogui.hotkey("ctrl", "v")
        except Exception:
            pass

def copy_and_paste(text, delay=PASTE_DELAY):
    """Copie et colle le texte avec espace intelligent avant le texte.
    
    Si le presse-papier se termine par un signe de ponctuation (. ! ? : ; ,)
    ou une lettre/chiffre, on préfixe automatiquement un espace pour éviter
    que le texte collé ne s'accroche au mot/ponctuation précédent.
    """
    if not text:
        return
    
    # Lire le contenu actuel du presse-papier
    prefix = ""
    try:
        prev = pyperclip.paste()
        if prev:
            last = prev[-1]
            if last.isalnum() or last in ".!?:;,)»\"'":
                prefix = " "
    except Exception:
        pass
    
    if not fast_copy(prefix + text):
        return
    
    # Restaurer le focus sur la fenêtre cible avant de coller
    if _restore_target_focus():
        # 80ms : minimum empirique pour que Windows traite le changement de focus
        time.sleep(0.08)
    else:
        # Délai standard si pas de fenêtre cible connue
        if delay > 0:
            time.sleep(delay)
    paste_text()

# ── Chargement & boucle principale ────────────────────────────────────────
def chargement():
    """Thread principal de chargement et transcription."""
    global detected_device, detected_compute
    
    # Vérifier le stream audio
    if stream[0] is None:
        set_statut_safe(tr("no_mic"), COLOR_RED, COLOR_RED)
        return
    
    if config["device"] != "auto":
        detected_device = config["device"]
        detected_compute = "float16" if detected_device == "cuda" else "int8"
    
    set_statut_safe(tr("loading_long"), COLOR_ORANGE, COLOR_ORANGE)
    
    # Charger le modèle avec fallback
    # TODO V1.4b : rendre le modèle global pour éviter rechargement par watchdog
    model = None
    try:
        model = WhisperModel(config["model"], device=detected_device, compute_type=detected_compute)
    except Exception as e:
        log_error(e, f"Impossible de charger le modèle {config['model']}")
        for fallback in ["base", "tiny"]:
            try:
                set_statut_safe(tr("fallback", model=fallback), COLOR_ORANGE, COLOR_ORANGE)
                model = WhisperModel(fallback, device="cpu", compute_type="int8")
                break
            except Exception:
                continue
    
    if model is None:
        set_statut_safe(tr("model_error"), COLOR_RED, COLOR_RED)
        return
    
    # Warmup
    set_statut_safe(tr("init", i=1, n=1), COLOR_ORANGE, COLOR_ORANGE)
    try:
        dummy_audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
        model.transcribe(dummy_audio, language=config["language"])
    except Exception as e:
        log_error(e)
    
    set_statut_safe(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)
    set_texte_safe("")
    
    while not _app_closing[0]:
        try:
            hotkey = config["hotkey"]
            
            # Attente raccourci ou mode réunion
            hotkey_pressed = is_hotkey_pressed(hotkey)
            while not hotkey_pressed and not mode_libre[0] and not _app_closing[0]:
                if hotkey_changed[0]:
                    hotkey_changed[0] = False
                    break
                time.sleep(POLL_INTERVAL)
                hotkey_pressed = is_hotkey_pressed(hotkey)
            
            if _app_closing[0]:
                break
            
            if not hotkey_pressed and not mode_libre[0]:
                continue
            
            # Capturer la fenêtre active IMMÉDIATEMENT (navigateur encore au 1er plan)
            if hotkey_pressed:
                _capture_target_window()

            # ── Verrou global anti-doublon ────────────────────────────────
            # _recording_lock est un threading.Event partagé entre tous les
            # threads. Si le watchdog relance chargement() pendant un enreg.,
            # le nouveau thread attend ici — pas de double transcription.
            if _recording_lock.is_set():
                time.sleep(POLL_INTERVAL)
                continue
            _recording_lock.set()   # acquérir le verrou

            set_statut_safe(tr("recording"), COLOR_RED, COLOR_RED)
            set_texte_safe("")
            audio_buffer.clear()
            is_recording.set()
            
            # ── Mode réunion ──────────────────────────────────────────────
            if mode_libre[0]:
                MAX_TICKS = int(MEETING_MAX_DURATION / MEETING_POLL)
                while mode_libre[0] and not _app_closing[0]:
                    silence_time    = 0.0
                    voice_time      = 0.0   # durée cumulée de parole dans ce segment
                    elapsed_ticks   = 0
                    last_voice_seen = False

                    # Attendre silence > seuil ET parole minimale capturée, OU durée max
                    while mode_libre[0] and not _app_closing[0]:
                        time.sleep(MEETING_POLL)
                        elapsed_ticks += 1

                        # Analyser les dernières 0.15s (un peu plus large = moins de faux silences)
                        recent = audio_buffer.get_data()
                        chunk_size = int(SAMPLE_RATE * 0.15)
                        recent_chunk = recent[-chunk_size:] if recent.size >= chunk_size else recent

                        voice_now = has_voice(recent_chunk)

                        if voice_now:
                            silence_time    = 0.0
                            last_voice_seen = True
                            voice_time     += MEETING_POLL
                        else:
                            if last_voice_seen:
                                silence_time += MEETING_POLL

                        # Couper si : silence suffisant ET parole minimale capturée
                        enough_voice   = voice_time >= MEETING_MIN_VOICE_DURATION
                        enough_silence = silence_time >= MEETING_SILENCE_THRESHOLD
                        if last_voice_seen and enough_silence and enough_voice:
                            break

                        # Couper si durée max atteinte
                        if elapsed_ticks >= MAX_TICKS:
                            break

                    if _app_closing[0]:
                        break

                    # ── Double buffer : snapshot audio puis redémarrer
                    # IMMÉDIATEMENT l'enregistrement avant la transcription
                    audio = audio_buffer.get_data()

                    if mode_libre[0] and not _app_closing[0]:
                        audio_buffer.clear()
                        is_recording.set()
                        set_statut_safe(tr("meeting_on"), COLOR_RED, COLOR_RED)
                    else:
                        is_recording.clear()

                    # Transcrire (le micro enregistre déjà le segment suivant)
                    if audio.size > 0 and last_voice_seen:
                        set_statut_safe(tr("transcribing"), COLOR_ORANGE, COLOR_ORANGE)
                        texte = transcribe_audio(model, audio)
                        if texte:
                            process_and_paste(texte)
                        if mode_libre[0] and not _app_closing[0]:
                            set_statut_safe(tr("meeting_on"), COLOR_RED, COLOR_RED)
                
                if _app_closing[0]:
                    break
                
                # Transcription finale
                audio = audio_buffer.get_data()
                is_recording.clear()
                
                if audio.size > 0:
                    set_statut_safe(tr("final_trans"), COLOR_ORANGE, COLOR_ORANGE)
                    texte = transcribe_audio(model, audio)
                    if texte:
                        process_and_paste(texte, delay=0.3)
                
                _recording_lock.clear()   # libérer le verrou après mode réunion
                set_statut_safe(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)
                continue

            # ── Mode push-to-talk ─────────────────────────────────────────
            while is_hotkey_pressed(hotkey) and not _app_closing[0]:
                time.sleep(POLL_INTERVAL)
            
            if _app_closing[0]:
                break
            
            # Copier l'audio avant de désactiver
            audio = audio_buffer.get_data()
            is_recording.clear()
            set_statut_safe(tr("transcribing"), COLOR_ORANGE, COLOR_ORANGE)
            
            if audio.size > 0:
                texte = transcribe_audio(model, audio)
                if texte:
                    process_and_paste(texte)
            
            # Purge du buffer + délai anti-rebond avant de libérer le verrou
            audio_buffer.clear()
            time.sleep(DEBOUNCE_DELAY)
            _recording_lock.clear()   # libérer le verrou

            set_statut_safe(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)
        
        except Exception as e:
            log_error(e)
            is_recording.clear()
            _recording_lock.clear()   # libérer même en cas d'erreur
            if not _app_closing[0]:
                set_statut_safe(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)
            time.sleep(0.5)

# ── Watchdog ──────────────────────────────────────────────────────────────
# Pré-cacher le HWND 500ms après démarrage (overrideredirect stabilisé)
root.after(500, _get_root_hwnd)
root.after(100, _install_mouse_hook)   # hook souris installé après démarrage mainloop

main_thread[0] = threading.Thread(target=chargement, daemon=True)
main_thread[0].start()

def watchdog():
    """Surveille le thread principal et le relance si nécessaire."""
    while not _app_closing[0]:
        time.sleep(5)
        if not _app_closing[0] and main_thread[0] and not main_thread[0].is_alive():
            log_error(msg="Thread mort — relance automatique")
            main_thread[0] = threading.Thread(target=chargement, daemon=True)
            main_thread[0].start()

threading.Thread(target=watchdog, daemon=True).start()

# ── Nettoyage VRAM (fix crash CUDA) — lancé une seule fois ───────────────
def vram_cleanup():
    """Nettoie la VRAM GPU toutes les 5 minutes pour éviter cudaErrorLaunchFailure."""
    try:
        import torch
        if not torch.cuda.is_available():
            return
    except Exception:
        return

    while not _app_closing[0]:
        time.sleep(300)  # 5 minutes
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass

threading.Thread(target=vram_cleanup, daemon=True).start()

# ── Démarrage ─────────────────────────────────────────────────────────────
root.mainloop()
