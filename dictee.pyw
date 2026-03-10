"""
Whisper Hélio v1.5 — Dictée vocale Windows 100% offline
Basé sur OpenAI Whisper / faster-whisper

Auteur : Hélio, Bretagne (France)
Projet Seattle (USA) 2028

Nouveautés v1.5 :
- Export multi-format (SRT, VTT, TXT horodaté, TXT brut, JSON)
  après transcription de fichier audio/vidéo
- Module core/export.py avec type hints et NamedTuple Segment

Historique v1.4b :
- Minimisation WinAPI, mode compact, dictionnaire lignes alternées
- Harmonisation UI/UX des fenêtres Macros / Actions / Dictionnaire
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import threading
import os
import time
import sys
import ctypes
import atexit
import faulthandler
from collections import deque
from pathlib import Path

# ── Filet segfault — capture les crashs C (ctranslate2, PortAudio) ───────
# faulthandler écrit le traceback natif dans le log au lieu de mourir en silence.
try:
    _FH_LOG = open(os.path.join(Path.home(), "whisper_helio_crash.log"), "a")
    faulthandler.enable(file=_FH_LOG)
except Exception:
    faulthandler.enable()   # fallback stderr

# ── tkinterdnd2 — drag-and-drop natif (Tcl/C, sans GIL issues) ────────────
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _HAS_DND = True
except ImportError:
    _HAS_DND = False

# ── AppUserModelID — DOIT être défini avant toute fenêtre ────────────────
# Sans cet ID, Windows associe l'icône au processus Python générique
# et affiche l'icône Python dans la taskbar au lieu de whisper_helio.ico
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "HelioDL.WhisperHelio.v15"
    )
except Exception:
    pass

# ── DPI Awareness ─────────────────────────────────────────────────────────
# SUPPRIMÉ : SetProcessDpiAwareness(2) rendait l'app DPI-aware (pixels physiques)
# mais Tkinter scale les polices par le facteur DPI → contenu tronqué à 150%+.
# Sans cet appel, Windows virtualise les coordonnées → fenêtre correcte partout.
# (Légèrement flou sur 4K mais fonctionnel sur toutes les résolutions.)

# ══════════════════════════════════════════════════════════════════════════
# FENÊTRE UNIQUE — cachée jusqu'à ce que l'UI soit 100% construite
# withdraw() immédiat → RIEN de visible → deiconify() à la fin → 1 fenêtre
# ══════════════════════════════════════════════════════════════════════════
root = TkinterDnD.Tk() if _HAS_DND else tk.Tk()
root.withdraw()   # Caché IMMÉDIATEMENT — rien n'apparaît à l'écran

# ── Import critique — si un module manque, message clair au lieu de crash
def _fatal_import(error: ImportError) -> None:
    """Affiche une erreur fatale d'import et quitte proprement."""
    try:
        import tkinter.messagebox as _mb
        _mb.showerror("Whisper Hélio", f"Module manquant : {error}\nRéinstallez l'application.")
    except Exception:
        pass
    sys.exit(1)

# Charger les modules avec progression
try:
    import sounddevice as sd
    import numpy as np
except ImportError as _ie:
    _fatal_import(_ie)

# keyboard remplacé par GetAsyncKeyState/keybd_event (zéro hook système)
try:
    import pyperclip
    import pyautogui
except ImportError as _ie:
    _fatal_import(_ie)

import math
import re
import socket
import subprocess
import ctypes.wintypes
import webbrowser
import gc
import signal
from tkinter import filedialog

# ── Recherche DLL CUDA pour le mode exe (cublas, cublasLt, cudart) ────────
# En mode dev, Python trouve ces DLL via torch dans le PATH.
# En mode exe compilé, on les cherche dans les emplacements connus.
_cuda_dll_found = False
if getattr(sys, 'frozen', False):
    _cuda_dll_dirs = []
    _home = str(Path.home())
    # 1) torch installé via pip (plusieurs versions Python possibles)
    for _pyver in ["Python313", "Python312", "Python311", "Python310"]:
        _py_base = os.path.join(
            _home, "AppData", "Local", "Programs", "Python",
            _pyver, "Lib", "site-packages")
        _cuda_dll_dirs.append(os.path.join(_py_base, "torch", "lib"))
        # nvidia-cublas-cu12 / nvidia-cuda-runtime-cu12 (pip install)
        _cuda_dll_dirs.append(os.path.join(_py_base, "nvidia", "cublas", "bin"))
        _cuda_dll_dirs.append(os.path.join(_py_base, "nvidia", "cublas", "lib"))
        _cuda_dll_dirs.append(os.path.join(_py_base, "nvidia", "cuda_runtime", "bin"))
        _cuda_dll_dirs.append(os.path.join(_py_base, "nvidia", "cuda_runtime", "lib"))
    _cuda_dll_dirs.append(os.path.join(sys.prefix, "Lib", "site-packages", "torch", "lib"))
    # 2) CUDA Toolkit NVIDIA — variable d'environnement
    _cuda_path = os.environ.get("CUDA_PATH", "")
    if _cuda_path:
        _cuda_dll_dirs.append(os.path.join(_cuda_path, "bin"))
    # 3) CUDA Toolkit — scan DYNAMIQUE de toutes les versions v12.x installées
    _cuda_base = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
    if os.path.isdir(_cuda_base):
        try:
            for _subdir in sorted(os.listdir(_cuda_base), reverse=True):
                if _subdir.startswith("v12"):
                    _cuda_dll_dirs.append(os.path.join(_cuda_base, _subdir, "bin"))
        except OSError:
            pass
    # Fallback : chemins explicites si le scan a échoué
    for _v in ["v12.9", "v12.8", "v12.7", "v12.6", "v12.5",
               "v12.4", "v12.3", "v12.2", "v12.1", "v12.0"]:
        _d = os.path.join(_cuda_base, _v, "bin")
        if _d not in _cuda_dll_dirs:
            _cuda_dll_dirs.append(_d)
    # 4) Dernier recours : scanner le PATH système (après reboot, CUDA Toolkit
    #    ajoute son dossier bin au PATH — fonctionne même si la version est inconnue)
    for _p in os.environ.get("PATH", "").split(os.pathsep):
        _p = _p.strip()
        if _p and _p not in _cuda_dll_dirs and os.path.isfile(os.path.join(_p, "cublas64_12.dll")):
            _cuda_dll_dirs.append(_p)

    _cuda_log = []   # diagnostic pour le crash log
    for _d in _cuda_dll_dirs:
        if os.path.isdir(_d) and os.path.exists(os.path.join(_d, "cublas64_12.dll")):
            _cuda_log.append(f"CUDA DLLs trouvees dans : {_d}")
            # Modifier PATH pour les DLL chargées par des extensions C
            os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")
            try:
                os.add_dll_directory(_d)
            except (OSError, AttributeError):
                pass
            # PRÉ-CHARGER les DLL CUDA en mémoire (la seule méthode fiable
            # dans un exe PyInstaller — les chemins PATH/add_dll_directory
            # ne suffisent pas car PyInstaller isole le chargement DLL)
            _loaded = []
            for _dll_name in ["cudart64_12.dll", "cublas64_12.dll", "cublasLt64_12.dll"]:
                _dll_path = os.path.join(_d, _dll_name)
                if os.path.exists(_dll_path):
                    try:
                        ctypes.CDLL(_dll_path)
                        _loaded.append(_dll_name)
                    except Exception as _e:
                        _cuda_log.append(f"  ECHEC chargement {_dll_name}: {_e}")
            _cuda_dll_found = bool(_loaded)
            _cuda_log.append(f"  Chargees: {', '.join(_loaded) if _loaded else 'AUCUNE'}")
            break
    if not _cuda_dll_found:
        _cuda_log.append("CUDA DLLs NON TROUVEES - mode CPU")
        _cuda_log.append(f"  CUDA_PATH={os.environ.get('CUDA_PATH', '(non defini)')}")
        _cuda_log.append(f"  Toolkit existe: {os.path.isdir(_cuda_base)}")
        if os.path.isdir(_cuda_base):
            try:
                _cuda_log.append(f"  Versions installees: {os.listdir(_cuda_base)}")
            except OSError:
                pass
    # Logger le diagnostic CUDA (visible dans le crash log)
    try:
        from core.config import LOG_FILE
        with open(LOG_FILE, "a", encoding="utf-8") as _f:
            for _line in _cuda_log:
                _f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [CUDA] {_line}\n")
    except Exception:
        pass

# faster_whisper : import LAZY dans _load_model() et _transcribe_file_worker()
# WhisperModel + ctranslate2 = ~1.5s d'import → déplacé dans le thread chargement
# L'import se fait en parallèle de l'affichage de la fenêtre.
_HAS_BATCHED = [None]   # None = pas encore testé, True/False après 1er essai

# Vérification version Python
if sys.version_info < (3, 8):
    root.withdraw()
    import tkinter.messagebox as _mb
    _mb.showerror("Whisper Hélio", "Python 3.8+ requis — installez Python 3.8 ou plus récent.")
    sys.exit(1)

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
POLL_INTERVAL = 0.015
DEBOUNCE_DELAY = 0.15    # 150ms suffit pour éviter les doubles déclenchements (avant: 300ms)
PASTE_DELAY = 0.05
VU_REFRESH_MS = 33
VU_IDLE_REFRESH_MS = 80    # rafraîchissement réduit au repos (pas besoin de 30fps)
ROUNDED_DELAY_MS = 50
WAVE_SPEED = 0.06
VU_DECAY = 0.82
CORNER_RADIUS = 18
TOOLTIP_DELAY_MS = 500
MINIMIZE_DELAY_MS = 150

# ── Dimensions boutons pill ──────────────────────────────────────────────
PILL_H         = 34     # hauteur standard bouton pill
PILL_H_LG      = 36     # hauteur large (boutons save)
PILL_FONT      = ("Segoe UI", 11, "bold")
PILL_FONT_LG   = ("Segoe UI", 14, "bold")
PILL_EMOJI_FONT = ("Segoe UI", 10)

# ── Couleurs boutons spéciaux ────────────────────────────────────────────
COLOR_SAVE      = "#2563eb"
COLOR_SAVE_HOVER = "#1d4ed8"
COLOR_GREY_HOVER = "#555555"

# ── Prompts initiaux pour transcription fichier (qualité max) ─────────────
# Le prompt initial guide le modèle vers un style de transcription formel
# avec ponctuation correcte. Technique recommandée par OpenAI pour améliorer
# significativement la précision sur la parole (réunions, discours, cours).
_FILE_INITIAL_PROMPTS = {
    "fr": "Transcription fidèle d'une conversation en français, avec une ponctuation correcte, des noms propres et des phrases complètes.",
    "en": "Accurate transcription of a conversation in English, with proper punctuation, capitalization, and complete sentences.",
    "es": "Transcripción fiel de una conversación en español, con puntuación correcta, nombres propios y oraciones completas.",
    "de": "Genaue Transkription eines Gesprächs auf Deutsch, mit korrekter Zeichensetzung, Eigennamen und vollständigen Sätzen.",
    "it": "Trascrizione fedele di una conversazione in italiano, con punteggiatura corretta, nomi propri e frasi complete.",
    "pt": "Transcrição fiel de uma conversa em português, com pontuação correta, nomes próprios e frases completas.",
    "nl": "Nauwkeurige transcriptie van een gesprek in het Nederlands, met correcte interpunctie, eigennamen en volledige zinnen.",
}

# ── PayPal ────────────────────────────────────────────────────────────────
PAYPAL_URL = "https://www.paypal.com/paypalme/heliostmalo"

# ── Instance unique ───────────────────────────────────────────────────────
# PAS de SO_REUSEADDR : sur Windows il permet plusieurs processus sur le
# même port, ce qui casse le verrou d'instance unique.
_lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _lock_socket.bind(("127.0.0.1", LOCK_PORT))
    _lock_socket.listen(1)   # LISTEN state — plus robuste comme verrou d'instance
except OSError:
    sys.exit(0)

# ── Config (module externe) ────────────────────────────────────────────────
from core.config import (
    HOME_DIR, BASE_DIR, CONFIG_FILE, LOG_FILE,
    DEFAULT_CONFIG, VALID_MODELS, VALID_HOTKEYS, VALID_THEMES,
    VALID_DEVICES, VALID_LANGUAGES, VALID_POSITIONS, VALID_UI_LANGS,
    MIN_W, MIN_H, MAX_WIN_W, MAX_WIN_H,
    validate_config, load_config, save_config,
    log_error, log_exception,
    regex_cache, invalidate_regex_cache,
)

sys.excepthook = log_exception
threading.excepthook = lambda args: log_exception(args.exc_type, args.exc_value, args.exc_traceback)

config = load_config()

# ── Audio (module externe) ─────────────────────────────────────────────────
from core.audio import (
    RingBuffer, has_voice,
    SAMPLE_RATE, MAX_RECORD_SECONDS, MIN_AUDIO_SAMPLES,
    AUDIO_BLOCKSIZE, VAD_THRESHOLD,
    MEETING_SILENCE_THRESHOLD, MEETING_MAX_DURATION, MEETING_POLL,
    MEETING_MIN_VOICE_DURATION, MEETING_GRACE_PERIOD, MEETING_GRACE_SILENCE,
)

# ── Système (module externe) ───────────────────────────────────────────────
from core.system import screen_scale, fit_window, create_desktop_shortcut
from core.export import EXPORT_FORMATS, export_files
from core.streaming import StreamingTranscriber
from core.macros import (
    BUILTIN_ACTIONS, apply_macros, apply_actions, apply_dictionary,
)
from core.hotkeys import is_hotkey_pressed, send_ctrl_v
from core.model import load_model as _load_model_core
from core.transcription import (
    transcribe_audio as _transcribe_audio_core,
    copy_and_paste as _copy_and_paste_core,
    fast_copy, paste_text,
)
_SCALE = screen_scale()
# Raccourci bureau : en background pour ne pas bloquer le démarrage
threading.Thread(target=create_desktop_shortcut, daemon=True).start()

# ── Traductions interface (module externe) ─────────────────────────────────
from i18n.translations import TRANSLATIONS, tr, set_lang_provider, clear_cache as _clear_tr_cache
set_lang_provider(lambda: config["ui_lang"])

# ── UI modules (late-binding -- fonctions utilisent ui.* au runtime) ───
import ui
import ui.winapi  # -> ctypes argtypes/restypes + sets ui._u32

from ui.winapi import (
    get_root_hwnd as _get_root_hwnd,
    capture_target_window as _capture_target_window,
    restore_target_focus as _restore_target_focus,
    destroy_icons as _destroy_icons,
    get_edge, CURSOR_MAP, BORDER,
    GWL_EXSTYLE as _GWL_EXSTYLE,
    WS_EX_APPWINDOW as _WS_EX_APPWINDOW,
    WS_EX_TOOLWINDOW as _WS_EX_TOOLWINDOW,
    WS_EX_NOACTIVATE as _WS_EX_NOACTIVATE,
    invalidate_hwnd_cache as _invalidate_hwnd_cache,
)
from ui.helpers import (
    _draw_pill, _create_pill_button,
    _finalize_toplevel, _bind_toplevel_drag,
    _apply_rounded_toplevel, _bind_rounded_toplevel,
    _make_scroll_area,
)
from ui.dialogs import open_help

# -- Phase 1 ui.init() -- references disponibles immediatement ---------
ui.init(
    root=root, config=config, theme=theme, tr=tr,
    log_error=log_error, save_config=save_config,
    fit_window=fit_window, _SCALE=_SCALE,
    _clear_tr_cache=_clear_tr_cache,
    _current_theme=_current_theme,
)


# ── Tooltips légers ──────────────────────────────────────────────────────
_tooltip_win = [None]   # fenêtre tooltip active (Toplevel ou None)
_tooltip_job = [None]   # after() id pour le délai d'apparition

def _tooltip_bind(widget, tr_key):
    """Ajoute un tooltip traduit à un widget (apparaît après 500ms au survol)."""
    def _show(e):
        _tooltip_cancel()
        def _display():
            if _app_closing[0]:
                return
            tw = tk.Toplevel(widget)
            tw.overrideredirect(True)
            tw.attributes("-topmost", True)
            t = theme()
            bg = t.get("btn_icon_bg", "#2a2a3e")
            fg = t.get("fg", "white")
            lbl = tk.Label(tw, text=tr(tr_key), bg=bg, fg=fg,
                           font=("Segoe UI", 8), padx=6, pady=3,
                           relief="solid", bd=1)
            lbl.pack()
            # Positionner sous le widget
            x = widget.winfo_rootx() + widget.winfo_width() // 2
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            tw.geometry(f"+{x - tw.winfo_reqwidth() // 2}+{y}")
            _tooltip_win[0] = tw
        _tooltip_job[0] = widget.after(500, _display)

    def _hide(e):
        _tooltip_cancel()

    widget.bind("<Enter>", _show, add="+")
    widget.bind("<Leave>", _hide, add="+")
    widget.bind("<Button-1>", _hide, add="+")

def _tooltip_cancel():
    """Annule le timer et détruit le tooltip s'il existe."""
    if _tooltip_job[0]:
        try:
            root.after_cancel(_tooltip_job[0])
        except Exception:
            pass
        _tooltip_job[0] = None
    if _tooltip_win[0]:
        try:
            _tooltip_win[0].destroy()
        except Exception:
            pass
        _tooltip_win[0] = None


# ── Détection matériel ────────────────────────────────────────────────────
def init_device() -> tuple[str, str, str]:
    """Initialise le device et détecte le matériel disponible.
    La vraie vérification CUDA se fait au warmup (DLL cublas, etc.).
    Returns (device, compute_type, hw_info_str).
    """
    dev = config["device"]
    if dev in ("cuda", "auto"):
        try:
            import ctranslate2 as _ct2
            gpu_count = _ct2.get_cuda_device_count()
            if gpu_count > 0:
                gpu_name = "NVIDIA GPU"
                # Méthode 1 : torch (mode dev)
                try:
                    import torch
                    if torch.cuda.is_available():
                        gpu_name = torch.cuda.get_device_name(0)
                    else:
                        raise RuntimeError("torch CUDA non disponible")
                except Exception:
                    # Méthode 2 : nvidia-smi (mode exe, ou torch sans CUDA)
                    try:
                        _nvsmi = subprocess.run(
                            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                            capture_output=True, text=True, timeout=5,
                            creationflags=0x08000000  # CREATE_NO_WINDOW
                        )
                        if _nvsmi.returncode == 0 and _nvsmi.stdout.strip():
                            gpu_name = _nvsmi.stdout.strip().split("\n")[0]
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

# init_device() déplacé dans chargement() — la fenêtre apparaît ~0.5s plus vite
# Placeholders mis à jour par le thread chargement
detected_device, detected_compute, hw_info = "auto", "auto", ""

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
        "input_bg": "#2d2d44",    # fond Entry/OptionMenu
        "input_fg": "white",
        "input_hover": "#3d3d54", # OptionMenu hover
        "vu_pill_bg": "#111120",  # fond pill VU-mètre
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
        "input_bg": "#dde3ea",    # fond Entry/OptionMenu
        "input_fg": "#1a1a2e",
        "input_hover": "#cdd3da", # OptionMenu hover
        "vu_pill_bg": "#d8dfe6",  # fond pill VU-mètre
    }
}

# Cache du thème courant
_current_theme = [None]

def theme() -> dict[str, str]:
    """Retourne le thème courant (avec cache)."""
    theme_name = config["theme"]
    if _current_theme[0] is None or _current_theme[0][0] != theme_name:
        _current_theme[0] = (theme_name, THEMES.get(theme_name, THEMES["dark"]))
    return _current_theme[0][1]

# ── Position de démarrage ─────────────────────────────────────────────────
def get_start_pos(w: int, h: int, sw: int, sh: int, position: str) -> tuple[int, int]:
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

# ── Configuration fenêtre principale (root créé au splash, ligne 61) ──────
# root est déjà un TkinterDnD.Tk() — on reconfigure pour l'UI principale

# ── Filet Tkinter — capture exceptions dans les callbacks after()/bind() ──
# Par défaut Tkinter les imprime sur stderr (invisible dans l'exe sans console).
def _tk_exception_handler(exc_type, exc_value, exc_tb):
    log_exception(exc_type, exc_value, exc_tb)
root.report_callback_exception = _tk_exception_handler

root.title("Whisper Hélio v1.5")
try:
    root.iconbitmap(str(BASE_DIR / "whisper_helio.ico"))
except (tk.TclError, FileNotFoundError, OSError):
    pass

root.attributes("-topmost", True)
root.overrideredirect(True)
root.configure(bg=theme()["bg"])

# ══════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════
# MINIMISATION TASKBAR — WinAPI directe sur root (v1.5 — sans proxy)
# ══════════════════════════════════════════════════════════════════════════
# Architecture v1.5 : on manipule DIRECTEMENT le HWND de root.
#   État normal   → WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE sur root
#                   → root invisible de la taskbar et Alt+Tab
#   Minimisation  → on retire WS_EX_TOOLWINDOW, on ajoute WS_EX_APPWINDOW
#                   → root apparaît dans la taskbar, puis ShowWindow(MINIMIZE)
#   Restauration  → ShowWindow(RESTORE), on remet WS_EX_TOOLWINDOW
#                   → root disparaît à nouveau de la taskbar
# Avantage : zéro fenêtre proxy, zéro doublon, comportement prévisible.
# ──────────────────────────────────────────────────────────────────────────
_u32 = ui._u32  # alias local (utilise dans minimize/restore/on_close)
_ICO_PATH = str(BASE_DIR / "whisper_helio.ico")   # pathlib -> str pour WinAPI

def _apply_icon_to_hwnd(hwnd: int) -> None:
    """Applique whisper_helio.ico via triple methode (-> ui.winapi)."""
    ui.winapi.apply_icon_to_hwnd(hwnd, _ICO_PATH)


def minimize_to_taskbar() -> None:
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
    # En mode compact, sauvegarder les dimensions complètes (pas les compactes)
    _save_w = _full_width[0]  if _compact_mode[0] and _full_width[0]  else root.winfo_width()
    _save_h = _full_height[0] if _compact_mode[0] and _full_height[0] else root.winfo_height()
    _saved_geom[0] = (root.winfo_x(), root.winfo_y(), _save_w, _save_h)

    # Étape 1 : invisible (évite le flash de la barre titre Windows)
    root.attributes("-alpha", 0)
    root.update_idletasks()

    # Étape 2 : overrideredirect(False) → Windows peut maintenant créer
    # un bouton taskbar. DÉCLENCHE <Map> mais _minimizing le bloque.
    root.overrideredirect(False)

    def _do_iconify():
        """Appelé 50ms après overrideredirect(False) — events Tkinter vidés."""
        if _app_closing[0]:
            return
        # Invalider le cache — overrideredirect change le HWND du cadre
        _root_hwnd[0] = None
        hwnd = _get_root_hwnd()

        # Appliquer WS_EX_APPWINDOW → force l'entrée dans la taskbar
        if hwnd:
            try:
                ex = _u32.GetWindowLongPtrW(hwnd, _GWL_EXSTYLE)
                ex = (ex & ~_WS_EX_TOOLWINDOW) | _WS_EX_APPWINDOW
                _u32.SetWindowLongPtrW(hwnd, _GWL_EXSTYLE, ex)
            except Exception as e:
                log_error(e, "SetWindowLongPtrW WS_EX_APPWINDOW")

        # Appliquer l'icône AVANT iconify via iconbitmap (Tkinter natif)
        # Windows utilise cette icône pour le bouton taskbar qu'il va créer
        try:
            root.iconbitmap(_ICO_PATH)
        except Exception as e:
            log_error(e, "iconbitmap minimize")

        # Minimiser — Windows crée le bouton taskbar avec l'icône déjà définie
        root.iconify()

        # Double application après iconify (certains Windows la réinitialisent)
        def _reinforce_icon():
            if _app_closing[0]:
                return
            _root_hwnd[0] = None   # re-invalider — iconify peut changer le handle
            h = _get_root_hwnd()
            _apply_icon_to_hwnd(h)
            root.after(150, lambda: None if _app_closing[0] else _minimizing.__setitem__(0, False))

        root.after(100, _reinforce_icon)

    root.after(50, _do_iconify)

def restore_from_taskbar(event=None):
    """Restaure root depuis la taskbar — appelé par <Map>."""
    # Bloquer pendant la séquence de minimisation ou la fermeture
    if _app_closing[0] or _minimizing[0] or not _minimized[0]:
        return
    _minimized[0] = False

    # Remettre overrideredirect (supprime la barre titre Windows)
    root.overrideredirect(True)
    _root_hwnd[0] = None   # HWND change à nouveau

    # Restaurer géométrie
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    if _compact_mode[0]:
        # Mode compact : restaurer les dimensions compactes, PAS les pleines
        _compact_w = max(120, (_full_width[0] or 300) // 3)
        x = _saved_geom[0][0] if _saved_geom[0] else config.get("win_x", 100)
        y = _saved_geom[0][1] if _saved_geom[0] else config.get("win_y", 100)
        x = max(0, min(x, sw - _compact_w))
        y = max(0, min(y, sh - 40))
        root.geometry(f"{_compact_w}x40+{x}+{y}")
        root.minsize(_compact_w, 40)
        root.maxsize(_compact_w, 40)
    else:
        if _saved_geom[0]:
            x, y, w, h = _saved_geom[0]
        else:
            w = config.get("win_w", max(650, min(1000, int(sw * 0.65))))
            h = config.get("win_h", max(280, int(320 * _SCALE)))
            x = config.get("win_x", 100)
            y = config.get("win_y", 100)
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
_t_init = theme()
style.configure("g.Horizontal.TProgressbar", troughcolor=_t_init.get("input_bg", "#2d2d44"), background='#2ecc71')
style.configure("TCombobox", fieldbackground=_t_init.get("input_bg", "#2d2d44"), background=_t_init.get("input_bg", "#2d2d44"))

screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()

_default_w = max(650, min(1000, int(screen_w * 0.65)))
_default_h = max(280, int(320 * _SCALE))
saved_w = config.get("win_w", _default_w)
saved_h = config.get("win_h", _default_h)
saved_w = max(MIN_W, saved_w)
saved_h = max(MIN_H, saved_h)
# S'assurer que ça tient dans l'écran
saved_w, saved_h = fit_window(saved_w, saved_h, screen_w, screen_h)

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
_file_transcribe_window = [None]   # Toplevel résultats transcription fichier
_help_window = [None]              # Toplevel aide/README

# -- Phase 2 ui.init() -- refs fenetres et etat -------------------------
ui.init(
    _app_closing=_app_closing,
    _help_window=_help_window,
    _settings_window=_settings_window,
    _macros_window=_macros_window,
    _file_transcribe_window=_file_transcribe_window,
)

_file_transcribing = threading.Lock()  # verrou anti-doublon transcription fichier (atomique)

# Derniers segments de transcription fichier (pour export)
_last_file_segments = [None]   # list[(text, start, end)] ou None
_last_file_path     = [None]   # chemin du fichier audio source ou None

# Verrou global anti-doublon transcription
# threading.Lock — acquire(blocking=False) est atomique (pas de TOCTOU)
_recording_lock = threading.Lock()

def on_close() -> None:
    """Ferme proprement l'application."""
    if _app_closing[0]:
        return   # re-entry guard (Ctrl+C + bouton fermer simultanés)
    _app_closing[0] = True

    # ── Lire la géométrie AVANT de cacher la fenêtre ──────────────────
    if _minimized[0] and _saved_geom[0]:
        x_save, y_save, w_save, h_save = _saved_geom[0]
    else:
        w_save = _full_width[0]  if _compact_mode[0] and _full_width[0]  else root.winfo_width()
        h_save = _full_height[0] if _compact_mode[0] and _full_height[0] else root.winfo_height()
        x_save, y_save = root.winfo_x(), root.winfo_y()

    # ── Disparition IMMÉDIATE — feedback visuel instantané ────────────
    try:
        root.withdraw()
    except Exception:
        pass
    for win_ref in (_settings_window, _macros_window, _file_transcribe_window, _help_window):
        try:
            if win_ref[0] is not None:
                win_ref[0].withdraw()
        except Exception:
            pass

    # Filet de sécurité : si le nettoyage bloque >3s, forcer la sortie
    def _force_exit():
        time.sleep(3)
        os._exit(0)
    threading.Thread(target=_force_exit, daemon=True).start()

    # ── Sauvegarder config (essentiel) ────────────────────────────────
    w_save = max(MIN_W, w_save)
    h_save = max(MIN_H, h_save)
    for k, v in (("win_x", x_save), ("win_y", y_save),
                 ("win_w", w_save), ("win_h", h_save)):
        config[k] = v
    save_config(config)

    # ── Libérer les ressources système ────────────────────────────────
    # abort() au lieu de stop() — coupe immédiatement sans attendre
    # la fin du buffer audio (stop() peut bloquer jusqu'à 256ms)
    for closer in (
        lambda: stream[0] and stream[0].abort(),
        lambda: stream[0] and stream[0].close(),
        lambda: _destroy_icons(),  # libere HICON caches (ui.winapi)
        lambda: _lock_socket.close(),
    ):
        try:
            closer()
        except Exception:
            pass

    # Sortie immédiate — empêche les extensions C (PortAudio, ctranslate2,
    # tkinterdnd2) de bloquer le processus pendant leur cleanup interne.
    # Pas besoin de root.destroy() ni cancel des after() — os._exit() tue tout.
    os._exit(0)

# Gestion Ctrl+C
def signal_handler(sig, frame):
    """Gère le signal SIGINT (Ctrl+C) — schedule on_close dans le mainloop.
    NE PAS mettre _app_closing=True ici : on_close() le fait lui-même,
    et le mettre avant empêcherait on_close() de faire le cleanup.
    """
    try:
        root.after(0, on_close)
    except Exception:
        os._exit(1)

try:
    signal.signal(signal.SIGINT, signal_handler)
except Exception:
    pass

root.protocol("WM_DELETE_WINDOW", on_close)

# ── Coins arrondis + NoActivate ───────────────────────────────────────────
def apply_rounded(event: tk.Event | None = None) -> None:
    """Applique coins arrondis + WS_EX_TOOLWINDOW + WS_EX_NOACTIVATE (-> ui.winapi)."""
    ui.winapi.apply_rounded(event)

_rounded_job = [None]
_last_rounded = [0]

def schedule_rounded(event: tk.Event | None = None) -> None:
    """Planifie l'application des coins arrondis avec debounce."""
    if _app_closing[0]:
        return
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
# BORDER, CURSOR_MAP, get_edge -> importes de ui.winapi


_current_cursor = [""]

def set_cursor(cursor: str) -> None:
    """Change le curseur seulement si différent."""
    if cursor != _current_cursor[0]:
        root.config(cursor=cursor)
        _current_cursor[0] = cursor

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

# ── Gauche : bouton Aide (❓) ─────────────────────────────────────────────
frame_left = tk.Frame(frame_top, bg=theme()["bg"])
frame_left.pack(side="left", padx=(0, 4))

btn_help = tk.Canvas(frame_left, width=28, height=28, bg=theme()["bg"],
                     highlightthickness=0, cursor="hand2")
btn_help.pack()
btn_help_bg  = btn_help.create_oval(2, 2, 26, 26,
                                    fill=theme().get("btn_icon_bg", "#2a2a3e"), outline="")
btn_help_txt = btn_help.create_text(14, 14, text="?",
                                    fill=theme()["btn_fg"],
                                    font=("Segoe UI", 11, "bold"))

def on_help_enter(e):
    btn_help.itemconfig(btn_help_bg, fill=COLOR_BLUE)
    btn_help.itemconfig(btn_help_txt, fill=COLOR_WHITE)
def on_help_leave(e):
    btn_help.itemconfig(btn_help_bg, fill=theme().get("btn_icon_bg", "#2a2a3e"))
    btn_help.itemconfig(btn_help_txt, fill=theme()["btn_fg"])
btn_help.bind("<Enter>", on_help_enter)
btn_help.bind("<Leave>", on_help_leave)
btn_help.bind("<Button-1>", lambda e: open_help())

# ── Centre : titre + hw + voyant + statut (tout centré) ──────────────────
frame_center = tk.Frame(frame_top, bg=theme()["bg"])
frame_center.pack(side="left", expand=True)

title_label = tk.Label(frame_center, text="Whisper Hélio v1.5",
                       fg=theme().get("fg_title", COLOR_WHITE),
                       bg=theme()["bg"], font=("Segoe UI", 19, "bold"))
title_label.pack()

hw_label = tk.Label(frame_center, text=hw_info,
                    fg="#9b59b6" if config["theme"] == "dark" else "#7b2d8e",
                    bg=theme()["bg"], font=("Segoe UI", 13))
hw_label.pack()

# Voyant + statut centrés sous hw_label
frame_statut = tk.Frame(frame_center, bg=theme()["bg"])
frame_statut.pack(pady=(3, 0))

voyant = tk.Canvas(frame_statut, width=12, height=12, bg=theme()["bg"], highlightthickness=0)
voyant.pack(side="left", pady=(1, 0))
cercle = voyant.create_oval(1, 1, 11, 11, fill=COLOR_GREEN, outline="")

statut_label = tk.Label(frame_statut, text=tr("loading"), fg=theme()["fg2"],
                        bg=theme()["bg"], font=("Segoe UI", 14))
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
_gear_color = theme()["btn_fg"]
_gear_ids   = _draw_gear(btn_settings, 16, 16, _gear_color)

def _recolor_gear(color):
    """Change la couleur de l'engrenage sans recréer les items (plus efficace)."""
    if len(_gear_ids) >= 2:
        btn_settings.itemconfig(_gear_ids[0], fill=color)       # polygon (corps)
        btn_settings.itemconfig(_gear_ids[1], outline=color)    # oval (trou central)

def on_settings_enter(e):
    btn_settings.itemconfig(btn_settings_bg, fill=COLOR_PURPLE)
    _recolor_gear(COLOR_WHITE)
def on_settings_leave(e):
    btn_settings.itemconfig(btn_settings_bg, fill=theme().get("btn_icon_bg","#2a2a3e"))
    _recolor_gear(theme()["btn_fg"])
btn_settings.bind("<Enter>", on_settings_enter)
btn_settings.bind("<Leave>", on_settings_leave)

# ── 3b. 📂 Bouton Transcrire fichier audio ─────────────────────────────
btn_file = tk.Canvas(frame_right, width=32, height=32, bg=theme()["bg"], highlightthickness=0, cursor="hand2")
btn_file.pack(side="left", padx=3)
btn_file_bg  = btn_file.create_oval(2, 2, 30, 30, fill=theme().get("btn_icon_bg", "#2a2a3e"), outline="")
btn_file_txt = btn_file.create_text(16, 16, text="\U0001F4C2", fill=theme()["btn_fg"], font=("Segoe UI", 11))

def on_file_enter(e):
    btn_file.itemconfig(btn_file_bg, fill=COLOR_BLUE)
    btn_file.itemconfig(btn_file_txt, fill=COLOR_WHITE)
def on_file_leave(e):
    btn_file.itemconfig(btn_file_bg, fill=theme().get("btn_icon_bg", "#2a2a3e"))
    btn_file.itemconfig(btn_file_txt, fill=theme()["btn_fg"])
btn_file.bind("<Button-1>", lambda e: open_file_transcribe())
btn_file.bind("<Enter>", on_file_enter)
btn_file.bind("<Leave>", on_file_leave)

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
    if _app_closing[0]:
        return
    if _compact_mode[0]:
        # ── Restaurer mode normal ──
        _compact_mode[0] = False
        vu_canvas.unbind("<Double-Button-1>")
        # Remettre les limites normales avant de restaurer
        root.minsize(MIN_W, MIN_H)
        root.maxsize(MAX_WIN_W, MAX_WIN_H)
        vu_canvas.configure(height=56)
        # Forcer recréation des objets VU avec la hauteur normale (56px)
        _reset_vu_objects()
        # frame_top doit revenir AVANT vu_canvas dans l'ordre pack
        frame_top.pack(fill="x", padx=14, pady=(12, 0), before=vu_canvas)
        texte_label.pack(fill="x", padx=10, pady=(4, 0))
        donation_frame.pack(fill="x", side="bottom", padx=14, pady=(0, 10))
        _sw_tc = root.winfo_screenwidth()
        w = _full_width[0] or config.get("win_w", max(650, min(1000, int(_sw_tc * 0.65))))
        h = _full_height[0] or config.get("win_h", max(280, int(320 * _SCALE)))
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
        _compact_width = max(120, _full_width[0] // 3)
        vu_canvas.configure(height=34)
        # Forcer recréation des objets VU avec la nouvelle hauteur (34px)
        _reset_vu_objects()
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

# -- UI helpers (regex, pills, toplevel) -> importes de ui.helpers + ui.dialogs --

# -- Fenetre Aide -> ui.dialogs.open_help (importee en haut) --

# ── Tooltips sur les boutons du header ────────────────────────────────────
_tooltip_bind(btn_help,     "tooltip_help")
_tooltip_bind(btn_reunion,  "tooltip_meeting")
_tooltip_bind(btn_libre,    "tooltip_macros")
_tooltip_bind(btn_settings, "tooltip_settings")
_tooltip_bind(btn_file,     "tooltip_file")
_tooltip_bind(btn_minimize, "tooltip_minimize")
_tooltip_bind(btn_fermer,   "tooltip_close")

# ── Hotkey label ──────────────────────────────────────────────────────────
HOTKEY_LABELS = {"mouse_x1": "thumb_back", "mouse_x2": "thumb_fwd"}

def _hotkey_label() -> str:
    """Retourne le label du hotkey configuré."""
    h = config["hotkey"]
    if h in HOTKEY_LABELS:
        return tr(HOTKEY_LABELS[h])
    return h.upper()

# -- Phase 3b: _hotkey_label -> ui --
ui.init(_hotkey_label=_hotkey_label)

mode_libre = [False]
hotkey_changed = [False]
_last_toggle_time = [0]

def toggle_libre() -> None:
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
_button_canvases = {btn_fermer, btn_settings, btn_libre, btn_reunion, btn_minimize, btn_file, btn_help}


# ── VU mètre — pleine largeur, barres cyan ───────────────────────────────
vu_canvas = tk.Canvas(root, height=56, bg=theme()["bg"], highlightthickness=0)
vu_canvas.pack(fill="x", padx=0, pady=(8, 0))

vu_level = [0.0]
wave_offset = [0.0]
NB_BARRES = 48          # plus de barres, style screenshot
VU_HEIGHT = 56
BAR_WIDTH = 3
BAR_RADIUS = BAR_WIDTH // 2 + 1
BAR_DIAMETER = BAR_RADIUS * 2
VU_RMS_GAIN = 12   # gain empirique : parole typique (~0.02-0.08 RMS) → 0.0-1.0 VU
vu_width = [saved_w]
vu_height = [VU_HEIGHT]   # cache hauteur — évite winfo_height() à chaque frame

# Pré-calcul du profil bell (constant)
def bell(i, n):
    """Calcule le profil en cloche pour le VU-mètre."""
    x = (i - n / 2) / (n / 2)
    return math.exp(-x * x * 2.0)

BELL_PROFILE = [bell(i, NB_BARRES) for i in range(NB_BARRES)]

# Pré-calcul table sinus
SIN_TABLE_SIZE = 256
SIN_TABLE = [math.sin(i * 2 * math.pi / SIN_TABLE_SIZE) for i in range(SIN_TABLE_SIZE)]

# Constantes pré-calculées pour le hot path VU
_BAR_TAGS = tuple(f"bar_{i}" for i in range(NB_BARRES))
_WAVE_MOD = 2 * math.pi * 1000

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

def _reset_vu_objects():
    """Reinitialise le VU-metre (supprime tous les objets canvas)."""
    vu_objects_created[0] = False
    vu_bg_objects.clear()
    vu_bar_rects.clear()
    vu_bar_tops.clear()
    vu_bar_bottoms.clear()
    vu_canvas.delete("all")
    _vu_last_color[0] = None

def create_vu_objects():
    """Crée les objets du VU-mètre — ovale de fond + barres cyan dedans."""
    if vu_objects_created[0]:
        return

    w         = vu_width[0]
    _raw_h    = vu_canvas.winfo_height()
    h         = _raw_h if _raw_h >= 10 else VU_HEIGHT   # winfo_height()=1 avant mapping
    t         = theme()
    vu_color  = t.get("vu_color", "#22d3ee")

    # ── Ovale de fond (pill) centré ─────────────────────────────────────────
    pill_h    = h - 6          # hauteur de l'ovale
    pill_w    = min(w - 20, int(w * 0.72))   # largeur max 72% de la fenêtre
    ox        = (w - pill_w) // 2            # position x gauche
    oy        = (h - pill_h) // 2            # position y haut
    ox2       = ox + pill_w
    oy2       = oy + pill_h
    r_pill    = pill_h // 2    # rayon des coins = demi-hauteur → ovale parfait

    # Fond pill : 4 arcs + 1 rectangle central
    pill_bg = t.get("vu_pill_bg", "#111120")  # adapté au thème
    vu_bg_objects.append(vu_canvas.create_arc(ox, oy, ox + r_pill*2, oy2, start=90, extent=180, fill=pill_bg, outline=pill_bg))
    vu_bg_objects.append(vu_canvas.create_arc(ox2 - r_pill*2, oy, ox2, oy2, start=270, extent=180, fill=pill_bg, outline=pill_bg))
    vu_bg_objects.append(vu_canvas.create_rectangle(ox + r_pill, oy, ox2 - r_pill, oy2, fill=pill_bg, outline=pill_bg))

    # ── Barres dans la pill ─────────────────────────────────────────────────
    inner_margin = r_pill + 8    # laisser de la place dans les coins arrondis
    inner_w   = pill_w - inner_margin * 2
    if inner_w < BAR_WIDTH * 2:
        vu_objects_created[0] = True   # trop étroit pour des barres
        return
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
            x1, inner_mid - 5, x2, inner_mid - 5 + BAR_DIAMETER, fill=vu_color, outline="", tags=tag))
        vu_bar_bottoms.append(vu_canvas.create_oval(
            x1, inner_mid + 5 - BAR_DIAMETER, x2, inner_mid + 5, fill=vu_color, outline="", tags=tag))

    _vu_last_color[0] = None
    vu_objects_created[0] = True

def update_vu_objects():
    """Met à jour les positions et couleurs du VU-mètre (pleine largeur)."""
    if not vu_objects_created[0]:
        create_vu_objects()
        return

    w         = vu_width[0]
    h         = vu_height[0]   # cache — mis à jour par on_vu_configure
    pill_w    = min(w - 20, int(w * 0.72))
    ox        = (w - pill_w) // 2
    r_pill    = (h - 6) // 2
    inner_margin = r_pill + 8
    inner_w   = pill_w - inner_margin * 2
    inner_mid = h // 2
    max_h     = max(1, r_pill - 4)
    nb        = len(vu_bar_rects)   # nombre réel créé (adaptatif)
    gap       = max(2, (inner_w - nb * BAR_WIDTH) // max(1, nb - 1))
    total_bars_w = nb * BAR_WIDTH + (nb - 1) * gap
    start_x   = ox + (pill_w - total_bars_w) // 2
    level   = vu_level[0]
    offset  = wave_offset[0]
    _step   = BAR_WIDTH + gap   # pas entre barres (constant dans la boucle)

    # Couleur : cyan en base, orange si fort, rouge si saturé
    if level > 0.75:
        color = COLOR_RED
    elif level > 0.45:
        color = COLOR_ORANGE
    else:
        color = theme().get("vu_color", "#22d3ee")

    for i in range(nb):
        x1 = start_x + i * _step
        x2 = x1 + BAR_WIDTH
        profile = BELL_PROFILE[min(NB_BARRES - 1, i * NB_BARRES // nb)]
        wave  = 0.7 + 0.3 * fast_sin(offset + i * 0.5)
        idle  = profile * (2 + 1.5 * abs(fast_sin(offset * 0.5 + i * 0.4)))
        active = profile * level * max_h * wave * 2.8
        bar_h  = max(BAR_RADIUS, min(max(idle, active), max_h))

        vu_canvas.coords(vu_bar_rects[i],   x1, inner_mid - bar_h + BAR_RADIUS,     x2, inner_mid + bar_h - BAR_RADIUS)
        vu_canvas.coords(vu_bar_tops[i],    x1, inner_mid - bar_h,                  x2, inner_mid - bar_h + BAR_DIAMETER)
        vu_canvas.coords(vu_bar_bottoms[i], x1, inner_mid + bar_h - BAR_DIAMETER,   x2, inner_mid + bar_h)

    if color != _vu_last_color[0]:
        for i in range(nb):
            vu_canvas.itemconfig(_BAR_TAGS[i], fill=color)
        _vu_last_color[0] = color

_vu_configure_job = [None]   # debounce pour on_vu_configure

def on_vu_configure(e):
    """Met à jour la largeur/hauteur du VU-mètre (debounced 80ms)."""
    _changed = False
    if e.width > 10 and e.width != vu_width[0]:
        vu_width[0] = e.width
        _changed = True
    if e.height > 10 and e.height != vu_height[0]:
        vu_height[0] = e.height
        _changed = True
    if _changed:
        # Debounce : pendant un redimensionnement, <Configure> est émis à chaque
        # pixel → on retarde la recréation pour n'exécuter qu'une seule fois.
        if _vu_configure_job[0] is not None:
            try:
                vu_canvas.after_cancel(_vu_configure_job[0])
            except Exception:
                pass
        def _do_vu_reconfigure():
            _vu_configure_job[0] = None
            if vu_objects_created[0]:
                _reset_vu_objects()
        _vu_configure_job[0] = vu_canvas.after(80, _do_vu_reconfigure)

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
        
        wave_offset[0] = (wave_offset[0] + WAVE_SPEED) % _WAVE_MOD
        vu_level[0] *= VU_DECAY
        update_vu_objects()
    except Exception as e:
        if not getattr(update_vu, '_err_logged', False):
            log_error(e, "update_vu")
            update_vu._err_logged = True

    if not _app_closing[0]:
        # 33ms pendant l'enregistrement (animation fluide), 80ms au repos
        interval = VU_REFRESH_MS if is_recording.is_set() else VU_IDLE_REFRESH_MS
        root.after(interval, update_vu)

root.after(200, update_vu)

# ── Zone texte — police adaptative ────────────────────────────────────────
_TEXTE_FONT_BASE = 20    # taille de base (ref 1920px)
_TEXTE_FONT_MIN = 14     # minimum en compact/petit écran
texte_label = tk.Label(root, text="", fg=theme()["fg"], bg=theme()["bg"],
                       font=("Consolas", _TEXTE_FONT_BASE), wraplength=saved_w - 40,
                       justify="left", anchor="nw")
texte_label.pack(fill="both", expand=True, padx=10, pady=(4, 0))

_wraplength_job = [None]

def update_wraplength(event=None):
    """Ajuste le wraplength et la taille de police dynamiquement (debounce 100ms)."""
    if _app_closing[0]:
        return
    if _wraplength_job[0]:
        root.after_cancel(_wraplength_job[0])
    def _apply():
        w = root.winfo_width()
        new_width = w - 40
        texte_label.config(wraplength=max(200, new_width))
        # Police adaptative : proportionnelle à la largeur fenêtre
        font_size = max(_TEXTE_FONT_MIN, int(_TEXTE_FONT_BASE * w / 1920))
        texte_label.config(font=("Consolas", font_size))
        _wraplength_job[0] = None
    _wraplength_job[0] = root.after(100, _apply)

root.bind("<Configure>", lambda e: (schedule_rounded(e), update_wraplength(e)))

# ── Footer — style v2 : liens gauche + bouton pill cyan droite ───────────
VERSION = "v1.5"

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
                          font=("Segoe UI", 13), cursor="hand2")
donation_label.pack(side="left")
donation_label.bind("<Button-1>", open_donation)
donation_label._is_clickable = True

def _don_enter(e):
    donation_label.config(fg=COLOR_BLUE)
def _don_leave(e):
    donation_label.config(fg=theme()["link"])
donation_label.bind("<Enter>", _don_enter)
donation_label.bind("<Leave>", _don_leave)

version_label = tk.Label(frame_links, text=f"  •  {VERSION}  •  {time.localtime().tm_year}",
                         fg="#ffffff" if config["theme"] == "dark" else "#333333",
                         bg=theme()["bg"], font=("Segoe UI", 13))
version_label.pack(side="left")

# Lien site web
SITE_URL = "https://helioman.fr"

site_label = tk.Label(frame_links, text="  •  helioman.fr",
                      fg="#f1c40f" if config["theme"] == "dark" else "#b8860b",
                      bg=theme()["bg"], font=("Segoe UI", 13), cursor="hand2")
site_label.pack(side="left")
site_label.bind("<Button-1>", lambda e: webbrowser.open(SITE_URL))
site_label._is_clickable = True

_SITE_COLOR = "#f1c40f" if config["theme"] == "dark" else "#b8860b"
def _site_enter(e): site_label.config(fg=COLOR_BLUE)
def _site_leave(e): site_label.config(fg=_SITE_COLOR)
site_label.bind("<Enter>", _site_enter)
site_label.bind("<Leave>", _site_leave)

# ── UI complète — première et UNIQUE apparition de la fenêtre ─────────────
root.deiconify()
root.attributes('-alpha', 0.93)

# ── Thème ─────────────────────────────────────────────────────────────────
def apply_theme() -> None:
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
    _is_dark = config["theme"] == "dark"
    hw_label.configure(bg=bg, fg="#9b59b6" if _is_dark else "#7b2d8e")
    try: frame_statut.configure(bg=bg)
    except Exception: pass

    # Boutons header
    btn_icon_bg = t.get("btn_icon_bg", "#2a2a3e")
    btn_fermer.configure(bg=bg)
    btn_fermer.itemconfig(btn_fermer_bg,  fill=btn_icon_bg)
    btn_fermer.itemconfig(btn_fermer_txt, fill=t["btn_fg"])
    btn_settings.configure(bg=bg)
    btn_settings.itemconfig(btn_settings_bg,  fill=btn_icon_bg)
    _recolor_gear(t["btn_fg"])   # btn_settings_txt=None (remplacé par gear canvas items)

    # VU-mètre
    vu_canvas.configure(bg=bg)
    # Recréer les objets au prochain frame pour appliquer la nouvelle couleur
    _reset_vu_objects()

    # Zone texte
    texte_label.configure(bg=bg, fg=t["fg"])

    # Footer
    donation_frame.configure(bg=bg)
    sep_line.configure(bg=t["fg2"])
    bottom_container.configure(bg=bg)
    frame_links.configure(bg=bg)
    donation_label.configure(bg=bg, fg=t["link"])
    version_label.configure(bg=bg, fg="#ffffff" if _is_dark else "#333333")
    site_label.configure(bg=bg, fg="#f1c40f" if _is_dark else "#b8860b")
    # btn_libre (micro→macros) : fond icon_bg
    btn_libre.configure(bg=bg)
    btn_libre.itemconfig(btn_libre_bg,  fill=t.get("btn_icon_bg","#2a2a3e"))
    btn_libre.itemconfig(btn_libre_txt, fill=COLOR_WHITE)
    # btn_reunion (mode réunion) : vert ou rouge selon état
    btn_reunion.configure(bg=bg)
    btn_reunion.itemconfig(btn_reunion_bg, fill=COLOR_RED if mode_libre[0] else COLOR_GREEN)
    btn_reunion.itemconfig(btn_reunion_txt, fill=COLOR_WHITE)
    # btn_minimize
    btn_minimize.configure(bg=bg)
    btn_minimize.itemconfig(btn_minimize_bg,  fill=t.get("btn_icon_bg","#2a2a3e"))
    btn_minimize.itemconfig(btn_minimize_txt, fill=t["btn_fg"])

    # btn_file (transcription fichier)
    btn_file.configure(bg=bg)
    btn_file.itemconfig(btn_file_bg,  fill=t.get("btn_icon_bg", "#2a2a3e"))
    btn_file.itemconfig(btn_file_txt, fill=t["btn_fg"])
    # btn_help (aide)
    btn_help.configure(bg=bg)
    btn_help.itemconfig(btn_help_bg,  fill=btn_icon_bg)
    btn_help.itemconfig(btn_help_txt, fill=t["btn_fg"])

    root.update_idletasks()

# ── Fonctions UI thread-safe ──────────────────────────────────────────────
def set_statut(texte: str, couleur: str, voyant_couleur: str) -> None:
    """Met à jour le statut (appeler depuis le thread principal)."""
    statut_label.config(text=texte, fg=couleur)
    voyant.itemconfig(cercle, fill=voyant_couleur)

def set_texte(texte: str) -> None:
    """Met à jour le texte de transcription."""
    texte_label.config(text=texte)

def _safe_after(delay_ms: int, callback: callable) -> None:
    """Planifie callback via root.after() en toute sécurité.
    Ignore silencieusement les TclError si la fenêtre est déjà détruite
    (évite les crashs pendant la fermeture de l'app).
    """
    if _app_closing[0]:
        return
    try:
        root.after(delay_ms, callback)
    except Exception:
        pass   # fenêtre détruite — normal pendant on_close()

def set_statut_safe(texte: str, couleur: str, voyant_couleur: str) -> None:
    """Met à jour le statut de manière thread-safe."""
    _safe_after(0, lambda: None if _app_closing[0] else set_statut(texte, couleur, voyant_couleur))

def set_texte_safe(texte: str) -> None:
    """Met à jour le texte de manière thread-safe."""
    _safe_after(0, lambda: None if _app_closing[0] else set_texte(texte))

# -- Phase 3 ui.init() -- fonctions UI thread-safe ---------------------
ui.init(
    set_statut_safe=set_statut_safe,
    set_texte_safe=set_texte_safe,
    _safe_after=_safe_after,
    apply_theme=apply_theme,
    _hotkey_label=_hotkey_label,
)


# -- Fenetre Parametres (-> ui.dialogs.open_settings) ----------------------
def open_settings() -> None:
    """Ouvre la fenetre des parametres (-> ui.dialogs.open_settings)."""
    from ui.dialogs import open_settings as _open_settings_ui

    def _on_save(new_settings, streaming_enabled):
        """Callback : applique les settings et met a jour l'UI."""
        for key, val in new_settings.items():
            config[key] = val
        config["streaming"] = streaming_enabled
        _streamer.enabled = config["streaming"]
        _streamer.set_language(config["language"])
        if _streamer.enabled and not _streamer.is_ready:
            _streamer.load_async()
        _current_theme[0] = None
        _clear_tr_cache()
        try:
            apply_theme()
        except Exception:
            pass
        save_config(config)
        title_label.config(text=tr("title"))
        donation_label.config(text=tr("support"))
        hotkey_changed[0] = True
        set_statut(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)

    _open_settings_ui(hw_info=hw_info, streamer=_streamer, on_save=_on_save)

btn_settings.bind("<Button-1>", lambda e: open_settings())

# ══════════════════════════════════════════════════════════════════════════
# TRANSCRIPTION DE FICHIER AUDIO (MP3, WAV, FLAC, OGG, M4A...)
# ══════════════════════════════════════════════════════════════════════════

# Extensions audio supportées par faster-whisper (via PyAV / ffmpeg)
_AUDIO_EXTENSIONS = (
    "*.mp3", "*.wav", "*.flac", "*.ogg", "*.m4a",
    "*.wma", "*.aac", "*.webm", "*.opus", "*.mp4",
)
_AUDIO_EXT_SET = {e.replace("*", "") for e in _AUDIO_EXTENSIONS}
# → {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".wma", ".aac", ".webm", ".opus", ".mp4"}


# ── Drag-and-drop fichiers audio (tkinterdnd2) ───────────────────────────

def _setup_drag_drop():
    """Active le drag-and-drop de fichiers audio via tkinterdnd2.

    tkinterdnd2 charge l'extension Tcl 'tkdnd' au niveau C — le drop est
    gere entierement dans la boucle Tcl, SANS callback Python pendant
    GetMessage(). Aucun conflit GIL, compatible Python 3.13+ / Tkinter.
    """
    if not _HAS_DND:
        return  # tkinterdnd2 non installe — silencieux
    try:
        root.drop_target_register(DND_FILES)
        root.dnd_bind("<<Drop>>", _on_tkdnd_drop)
    except Exception:
        pass  # Drag-drop non disponible — pas critique


def _on_tkdnd_drop(event):
    """Callback tkinterdnd2 — recoit le chemin du fichier depose."""
    if _app_closing[0]:
        return
    raw = event.data
    if not raw or not raw.strip():
        return
    # tkinterdnd2 : chemins avec espaces → {C:/path with spaces/file.mp3}
    # Sans espaces → C:/path/file.mp3
    # Plusieurs fichiers séparés par espace (on prend le premier)
    raw = raw.strip()
    if raw.startswith("{"):
        # Extraire le contenu entre { et }
        end = raw.find("}")
        filepath = raw[1:end] if end > 0 else raw[1:]
    else:
        # Pas d'accolades : soit chemin simple, soit multiples séparés par espace
        # Vérifier d'abord si le chemin complet est un fichier (gère espaces sans accolades)
        if os.path.isfile(raw.replace("/", os.sep)):
            filepath = raw
        else:
            filepath = raw.split()[0]
    filepath = os.path.realpath(filepath.replace("/", os.sep))  # normaliser + résoudre ..
    _handle_dropped_file(filepath)


def _handle_dropped_file(filepath):
    """Traite un fichier depose par drag-and-drop sur la fenetre."""
    if _app_closing[0]:
        return
    if not os.path.isfile(filepath):
        return
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in _AUDIO_EXT_SET:
        set_statut_safe(tr("file_bad_format", ext=ext), COLOR_ORANGE, COLOR_ORANGE)
        return
    if not _file_transcribing.acquire(blocking=False):
        set_statut_safe(tr("file_busy_file"), COLOR_ORANGE, COLOR_ORANGE)
        return
    if _global_model[0] is None:
        _file_transcribing.release()
        set_statut_safe(tr("file_no_model"), COLOR_RED, COLOR_RED)
        return
    if is_recording.is_set() or mode_libre[0]:
        _file_transcribing.release()
        set_statut_safe(tr("file_busy_recording"), COLOR_ORANGE, COLOR_ORANGE)
        return
    filename = os.path.basename(filepath)
    set_statut_safe(tr("file_transcribing", name=filename[:30]), COLOR_BLUE, COLOR_BLUE)
    try:
        threading.Thread(target=_transcribe_file_worker, args=(filepath, filename),
                         daemon=True).start()
    except Exception:
        _file_transcribing.release()


def open_file_transcribe() -> None:
    """Ouvre un dialogue de sélection de fichier audio et lance la transcription."""
    # Vérifications préalables — acquire atomique (pas de TOCTOU)
    if not _file_transcribing.acquire(blocking=False):
        set_statut_safe(tr("file_busy_file"), COLOR_ORANGE, COLOR_ORANGE)
        return

    if _global_model[0] is None:
        _file_transcribing.release()
        set_statut_safe(tr("file_no_model"), COLOR_RED, COLOR_RED)
        return

    if is_recording.is_set() or mode_libre[0]:
        _file_transcribing.release()
        set_statut_safe(tr("file_busy_recording"), COLOR_ORANGE, COLOR_ORANGE)
        return

    # Retirer temporairement topmost pour que le filedialog soit visible
    root.attributes("-topmost", False)
    try:
        filepath = filedialog.askopenfilename(
            parent=root,
            title=tr("file_transcribe"),
            filetypes=[
                (tr("file_formats"), " ".join(_AUDIO_EXTENSIONS)),
                ("MP3",       "*.mp3"),
                ("WAV",       "*.wav"),
                ("FLAC",      "*.flac"),
                ("OGG/Opus",  "*.ogg *.opus"),
                ("M4A/AAC",   "*.m4a *.aac"),
                (tr("file_all_types"),  "*.*"),
            ]
        )
    except Exception:
        # filedialog a crashé — libérer le verrou et abandonner
        _file_transcribing.release()
        return
    finally:
        root.attributes("-topmost", True)

    # filedialog peut retourner "" (annulé) ou () (tuple sur certains Tk)
    if not filepath or not isinstance(filepath, str):
        _file_transcribing.release()
        return

    if not os.path.isfile(filepath):
        _file_transcribing.release()
        return

    # Lancer la transcription en arrière-plan
    if _app_closing[0]:
        _file_transcribing.release()
        return
    filename = os.path.basename(filepath)
    set_statut_safe(tr("file_transcribing", name=filename[:30]), COLOR_BLUE, COLOR_BLUE)

    try:
        threading.Thread(
            target=_transcribe_file_worker,
            args=(filepath, filename),
            daemon=True,
        ).start()
    except Exception:
        _file_transcribing.release()


_PAUSE_PARAGRAPH = 1.5     # pause longue → toujours nouveau paragraphe
_PAUSE_SENTENCE  = 0.8     # pause courte après fin de phrase → nouveau paragraphe
_SENTENCE_ENDS   = frozenset(".!?…»\")")


def _format_transcription(segments_data: list[tuple[str, float, float]]) -> str:
    """Met en forme le texte transcrit avec paragraphes automatiques.

    Utilise les timestamps des segments Whisper pour détecter les pauses
    naturelles (changement de sujet, pause oratoire, changement de locuteur)
    et insérer des sauts de ligne.

    Args:
        segments_data: liste de tuples (texte, start, end) — timestamps en secondes

    Returns:
        Texte formaté avec paragraphes (str)

    Seuils :
        - Pause ≥ 1.5s entre deux segments → nouveau paragraphe (\\n\\n)
        - Phrase qui finit par .!? suivie d'une pause ≥ 0.8s → nouveau paragraphe
        - Sinon les segments sont joints avec un espace
    """
    if not segments_data:
        return ""

    paragraphs = []
    current_para = [segments_data[0][0]]

    for i in range(1, len(segments_data)):
        prev_text, _, prev_end = segments_data[i - 1]
        curr_text, curr_start, _ = segments_data[i]

        pause = max(0.0, curr_start - prev_end)

        # Décision : nouveau paragraphe ou continuation ?
        new_para = False
        if pause >= _PAUSE_PARAGRAPH:
            # Pause longue → toujours nouveau paragraphe
            new_para = True
        elif pause >= _PAUSE_SENTENCE and prev_text and prev_text[-1] in _SENTENCE_ENDS:
            # Pause moyenne après fin de phrase → nouveau paragraphe
            new_para = True

        if new_para:
            paragraphs.append(" ".join(current_para))
            current_para = [curr_text]
        else:
            current_para.append(curr_text)

    # Dernier paragraphe
    if current_para:
        paragraphs.append(" ".join(current_para))

    # Capitaliser la première lettre de chaque paragraphe
    formatted = []
    for para in paragraphs:
        para = para.strip()
        if para and para[0].islower():
            para = para[0].upper() + para[1:]
        formatted.append(para)

    return "\n\n".join(formatted).strip()


def _transcribe_file_worker(filepath: str, filename: str) -> None:
    """Thread worker : transcrit un fichier audio et affiche les résultats.

    Stratégie d'accélération (v1.5) :
    1. BatchedInferencePipeline (si disponible) : traite N segments en parallèle
       sur le GPU. Le VAD Silero (CPU) découpe l'audio, le GPU traite en batch.
       → CPU et GPU travaillent simultanément en pipeline.
    2. Fallback séquentiel si BatchedInferencePipeline absent ou OOM.
    """
    try:
        model = _global_model[0]
        if model is None:
            set_statut_safe(tr("file_no_model"), COLOR_RED, COLOR_RED)
            return

        start_time = time.perf_counter()

        try:
            _lang = config["language"]

            # ── Paramètres communs ──
            _common_kwargs = dict(
                language=_lang,
                initial_prompt=_FILE_INITIAL_PROMPTS.get(_lang, ""),
                condition_on_previous_text=True,
                no_speech_threshold=0.55,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                repetition_penalty=1.3,   # 1.3 : réduit les répétitions sans casser les noms
            )

            # ── Tentative 1 : BatchedInferencePipeline (4-5x plus rapide) ──
            # GPU traite les segments en batch, CPU fait le VAD en parallèle
            # Lazy import de BatchedInferencePipeline (1ère utilisation seulement)
            if _HAS_BATCHED[0] is None:
                try:
                    from faster_whisper import BatchedInferencePipeline as _BIP
                    _HAS_BATCHED[0] = True
                    log_error(msg="[FILE] BatchedInferencePipeline disponible (lazy import OK)")
                except ImportError:
                    _HAS_BATCHED[0] = False
                    log_error(msg="[FILE] BatchedInferencePipeline non disponible")

            _used_batched = False
            if _HAS_BATCHED[0] and detected_device == "cuda":
                try:
                    from faster_whisper import BatchedInferencePipeline as _BIP
                    _batched = _BIP(model=model)
                    set_statut_safe(
                        tr("file_progress", pct=0, elapsed=0) + " [GPU batch]",
                        COLOR_BLUE, COLOR_BLUE
                    )
                    # batch_size=32 : RTX 5080 16Go VRAM (marge large)
                    # beam_size=1 + batch : ~20% plus rapide que beam=5, qualité OK
                    # VAD Silero intégré (filtre le silence automatiquement)
                    segments_gen, info = _batched.transcribe(
                        filepath,
                        batch_size=32,
                        beam_size=1,
                        temperature=(0, 0.2, 0.4),
                        **_common_kwargs,
                    )
                    _used_batched = True
                    log_error(msg=f"[FILE] Mode BatchedInference (batch=32, beam=1, GPU)")
                except Exception as _be:
                    # OOM ou autre erreur → fallback séquentiel
                    log_error(_be, "BatchedInferencePipeline échoué, fallback séquentiel")
                    _used_batched = False

            # ── Tentative 2 : séquentiel classique ──
            if not _used_batched:
                _seq_kwargs = dict(
                    beam_size=1,
                    temperature=(0, 0.4, 0.8),
                    vad_filter=False,
                    **_common_kwargs,
                )
                try:
                    segments_gen, info = model.transcribe(filepath, **_seq_kwargs)
                except TypeError:
                    for _k in ("repetition_penalty", "initial_prompt"):
                        _seq_kwargs.pop(_k, None)
                    segments_gen, info = model.transcribe(filepath, **_seq_kwargs)
                log_error(msg=f"[FILE] Mode séquentiel (beam=1, {detected_device})")

            audio_duration = getattr(info, 'duration', 0) or 0

            # ── Collecte des segments ──
            _segments_data = []
            _last_progress_time = time.perf_counter()
            _last_gc_time = time.perf_counter()
            _SEGMENT_TIMEOUT = 120

            gc.disable()
            try:
              for segment in segments_gen:
                if _app_closing[0]:
                    return
                if time.perf_counter() - _last_progress_time > _SEGMENT_TIMEOUT:
                    log_error(msg=f"Transcription fichier timeout ({_SEGMENT_TIMEOUT}s sans segment)")
                    set_statut_safe(tr("file_timeout"), COLOR_ORANGE, COLOR_ORANGE)
                    break

                _last_progress_time = time.perf_counter()
                seg_text = segment.text.strip()
                if seg_text:
                    _segments_data.append((seg_text, segment.start, segment.end))

                if time.perf_counter() - _last_gc_time > 60:
                    gc.enable()
                    gc.collect()
                    gc.disable()
                    _last_gc_time = time.perf_counter()

                if audio_duration > 0:
                    pct = min(99, int((segment.end / audio_duration) * 100))
                    elapsed = int(time.perf_counter() - start_time)
                    _mode = "batch" if _used_batched else "seq"
                    set_statut_safe(
                        tr("file_progress", pct=pct, elapsed=elapsed) + f" [{_mode}]",
                        COLOR_BLUE, COLOR_BLUE
                    )
            finally:
                gc.enable()

            result = _format_transcription(_segments_data)

            # Sauvegarder les segments pour l'export
            _last_file_segments[0] = list(_segments_data)
            _last_file_path[0] = filepath

        except Exception as e:
            log_error(e, f"Transcription fichier échouée: {filepath}")
            err_msg = str(e).lower()
            if "decode" in err_msg or "audio" in err_msg or "av" in err_msg or "ffmpeg" in err_msg:
                set_statut_safe(tr("file_error_decode"), COLOR_RED, COLOR_RED)
            else:
                set_statut_safe(
                    tr("file_error_generic", err=str(e)[:80]),
                    COLOR_RED, COLOR_RED
                )
            return

        if _app_closing[0]:
            return

        total_time = int(time.perf_counter() - start_time)
        _speed = f"{audio_duration/total_time:.1f}x" if total_time > 0 and audio_duration > 0 else ""
        set_statut_safe(
            tr("file_done", duration=total_time) + (f" ({_speed} temps réel)" if _speed else ""),
            COLOR_GREEN, COLOR_GREEN
        )

        if not _app_closing[0]:
            final_text = result if result else tr("file_empty")
            _safe_after(0, lambda: _show_file_result(filename, final_text))

    finally:
        _file_transcribing.release()


def _show_file_result(filename: str, text: str) -> None:
    """Affiche le résultat de transcription dans une fenêtre Toplevel."""
    if _app_closing[0]:
        return
    # Si une fenêtre est déjà ouverte, la remplacer
    if _file_transcribe_window[0] is not None:
        try:
            if _file_transcribe_window[0].winfo_exists():
                _file_transcribe_window[0].destroy()
        except Exception:
            pass

    t  = theme()
    bg = t["bg"]
    fg = t["fg"]
    fg2 = t["fg2"]

    win = tk.Toplevel(root)
    title_text = tr("file_result_title", name=filename[:40])
    win.title(title_text + " - Whisper Helio")
    win.configure(bg=bg)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.95)
    win.overrideredirect(True)
    win.resizable(True, True)

    _copy_feedback_job = [None]   # timer "Copié!" → annulé à la fermeture

    def on_close_file():
        _file_transcribe_window[0] = None   # déréférencer AVANT destroy
        if _copy_feedback_job[0]:
            try: win.after_cancel(_copy_feedback_job[0])
            except Exception: pass
        try:
            if hasattr(win, '_rounded_job') and win._rounded_job:
                win.after_cancel(win._rounded_job)
            win.destroy()
        except tk.TclError:
            pass
    win.protocol("WM_DELETE_WINDOW", on_close_file)

    # ── Barre de titre custom (drag + ✕) ─────────────────────────────────
    _hdr_pad = max(8, int(14 * _SCALE))
    frame_hdr_f = tk.Frame(win, bg=bg)
    frame_hdr_f.pack(fill="x", padx=_hdr_pad, pady=(12, 0))

    # Bouton ✕ packe EN PREMIER (side="right") pour etre toujours visible
    _btn_cls_f = tk.Canvas(frame_hdr_f, width=32, height=32, bg=bg,
                           highlightthickness=0, cursor="hand2")
    _btn_cls_f.pack(side="right", padx=(8, 4))
    _cls_bg_f  = _btn_cls_f.create_oval(2, 2, 30, 30, fill=COLOR_RED, outline="")
    _btn_cls_f.create_text(16, 16, text="\u2715", fill=COLOR_WHITE,
                           font=("Segoe UI", 11, "bold"))

    # PUIS le titre (ne pousse pas le ✕ hors vue)
    tk.Label(frame_hdr_f, text=title_text, bg=bg,
             fg=t.get("fg_title", fg), font=("Segoe UI", 13, "bold"),
             anchor="w").pack(side="left", fill="x", expand=True)

    def _cls_f_enter(e):
        _btn_cls_f.itemconfig(_cls_bg_f, fill=COLOR_RED_DARK)
    def _cls_f_leave(e):
        _btn_cls_f.itemconfig(_cls_bg_f, fill=COLOR_RED)
    _btn_cls_f.bind("<Enter>",    _cls_f_enter)
    _btn_cls_f.bind("<Leave>",    _cls_f_leave)
    _btn_cls_f.bind("<Button-1>", lambda e: on_close_file())

    _bind_toplevel_drag(frame_hdr_f, win)

    # Séparateur
    tk.Frame(win, height=1, bg=t.get("vu_color", "#22d3ee")).pack(
        fill="x", padx=_hdr_pad, pady=(8, 0))

    # ── Zone de texte scrollable ─────────────────────────────────────────
    # NB : text_frame est créé ici mais packé APRÈS le footer (side="bottom")
    # pour que les boutons soient toujours visibles (même pattern que open_macros)
    text_frame = tk.Frame(win, bg=bg)

    text_widget = tk.Text(
        text_frame, wrap="word",
        bg=t.get("input_bg", "#2d2d44"),
        fg=t.get("input_fg", "white"),
        font=("Consolas", 11),
        insertbackground=t.get("input_fg", "white"),
        relief="flat", bd=8,
        selectbackground=COLOR_BLUE,
        selectforeground=COLOR_WHITE,
    )
    _ft_sb = tk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
    text_widget.configure(yscrollcommand=_ft_sb.set)
    _ft_sb.pack(side="right", fill="y")
    text_widget.pack(side="left", fill="both", expand=True)

    text_widget.insert("1.0", text)

    # ── Footer fixe (AVANT text_frame dans le pack pour être toujours visible) ─
    # side="bottom" réserve l'espace depuis le bas → boutons toujours visibles
    footer = tk.Frame(win, bg=bg)
    footer.pack(fill="x", side="bottom", padx=12, pady=(4, 12))

    tk.Frame(footer, height=1, bg=fg2).pack(fill="x", pady=(0, 8))

    btn_frame = tk.Frame(footer, bg=bg)
    btn_frame.pack()

    # Bouton "Copier tout" — pill bleu (avec feedback "Copié!")
    _btn_copy = _create_pill_button(
        btn_frame, 150, PILL_H, tr("file_copy_all").upper(),
        COLOR_BLUE, COLOR_BLUE_DARK, bg=bg,
        emoji="\U0001F4CB", tag="cp",
        pack_opts={"side": "left", "padx": (0, 10)},
    )

    def _do_copy(e=None):
        content = text_widget.get("1.0", "end-1c")
        if content:
            try:
                pyperclip.copy(content)
                _btn_copy.itemconfig("txt_cp", text=tr("file_copied").upper())
                if _copy_feedback_job[0]:
                    try: win.after_cancel(_copy_feedback_job[0])
                    except Exception: pass
                _copy_feedback_job[0] = win.after(1500, lambda: _btn_copy.itemconfig(
                    "txt_cp", text=tr("file_copy_all").upper()))
            except Exception as exc:
                log_error(exc, "pyperclip.copy result")

    _btn_copy.bind("<Button-1>", _do_copy)  # callback custom (feedback "Copié!")

    # Bouton "Exporter" — pill vert (si segments disponibles)
    if _last_file_segments[0]:
        _create_pill_button(
            btn_frame, 150, PILL_H, tr("export_btn"),
            COLOR_GREEN, COLOR_GREEN_HOVER, bg=bg,
            emoji="\U0001F4BE", tag="ex",
            callback=lambda e: _show_export_dialog(win),
            pack_opts={"side": "left", "padx": (0, 10)},
        )

    # Bouton "Fermer" — pill rouge
    _create_pill_button(
        btn_frame, 120, PILL_H, tr("file_close").upper(),
        COLOR_RED, COLOR_RED_DARK, bg=bg, tag="cl",
        callback=lambda e: on_close_file(),
        pack_opts={"side": "left"},
    )

    # ── Pack text_frame APRÈS le footer → il prend l'espace restant ──
    text_frame.pack(fill="both", expand=True, padx=12, pady=(8, 4))

    # Raccourcis clavier
    win.bind("<Escape>", lambda e: on_close_file())
    text_widget.bind("<Control-a>",
                     lambda e: (text_widget.tag_add("sel", "1.0", "end"), "break"))

    # Taille, centrage, coins arrondis
    _finalize_toplevel(win, 600, 500)

    # Enregistrer la fenêtre APRÈS configuration complète (pas avant)
    _file_transcribe_window[0] = win


# ── Fenêtre Export ────────────────────────────────────────────────────────

def _open_folder(path: str) -> None:
    """Ouvre un dossier dans l'Explorateur Windows."""
    try:
        os.startfile(os.path.realpath(path))
    except Exception:
        pass   # pas critique


def _show_export_dialog(parent_win):
    """
    Affiche la fenêtre de sélection des formats d'export.

    Propose 5 formats (SRT, VTT, TXT horodaté, TXT brut, JSON)
    via des cases à cocher, exporte les fichiers dans le même dossier
    que le fichier audio source, et affiche un feedback visuel.
    """
    segments = _last_file_segments[0]
    source   = _last_file_path[0]
    if not segments or not source:
        return

    t  = theme()
    bg = t["bg"]
    fg = t["fg"]
    fg2 = t["fg2"]

    # Informations sur la source
    _src_dir  = os.path.dirname(source) or "."
    _src_name = os.path.splitext(os.path.basename(source))[0]
    _n_segs   = len(segments)
    _duration = max((end for _, _, end in segments), default=0.0)
    _dur_min  = int(_duration // 60)
    _dur_sec  = int(_duration % 60)

    dlg = tk.Toplevel(parent_win)
    dlg.title("Exporter — Whisper Hélio")
    dlg.configure(bg=bg)
    dlg.attributes("-topmost", True)
    dlg.attributes("-alpha", 0.95)
    dlg.overrideredirect(True)
    dlg.resizable(False, False)

    # ── En-tête (déplaçable) ──
    hdr = tk.Frame(dlg, bg=bg)
    hdr.pack(fill="x", padx=16, pady=(14, 6))
    tk.Label(hdr, text=f"💾  {tr('export_title')}",
             font=("Segoe UI", 13, "bold"), fg=fg, bg=bg).pack(anchor="w")
    _info_txt = f"{_n_segs} {tr('export_segments')} · {_dur_min}:{_dur_sec:02d}"
    tk.Label(hdr, text=_info_txt,
             font=("Segoe UI", 9), fg=fg2, bg=bg).pack(anchor="w")

    # ── Séparateur ──
    tk.Frame(dlg, height=1, bg=fg2).pack(fill="x", padx=16, pady=(6, 8))

    # ── Destination (modifiable) ──
    _dest_dir = [_src_dir]   # variable mutable — répertoire de sortie

    dest_frame = tk.Frame(dlg, bg=bg)
    dest_frame.pack(fill="x", padx=20, pady=(0, 8))
    tk.Label(dest_frame, text=tr("export_folder"),
             font=("Segoe UI", 9), fg=fg2, bg=bg).pack(side="left")

    def _short(path):
        return path if len(path) <= 40 else "…" + path[-37:]

    dest_lbl = tk.Label(dest_frame, text=_short(_dest_dir[0]),
                        font=("Consolas", 8), fg=COLOR_BLUE, bg=bg,
                        cursor="hand2")
    dest_lbl.pack(side="left", padx=(4, 0))
    dest_lbl.bind("<Button-1>", lambda e: _open_folder(_dest_dir[0]))

    def _browse_dest():
        dlg.attributes("-topmost", False)
        try:
            chosen = filedialog.askdirectory(
                parent=dlg,
                initialdir=_dest_dir[0],
                title=tr("export_browse"),
            )
        finally:
            dlg.attributes("-topmost", True)
        if chosen:
            _dest_dir[0] = chosen
            dest_lbl.configure(text=_short(chosen))

    btn_browse = tk.Label(dest_frame, text="📂", font=("Segoe UI", 11),
                          fg=fg2, bg=bg, cursor="hand2", padx=4)
    btn_browse.pack(side="left", padx=(4, 0))
    btn_browse.bind("<Button-1>", lambda e: _browse_dest())

    # ── Cases à cocher des formats ──
    checks_frame = tk.Frame(dlg, bg=bg)
    checks_frame.pack(fill="x", padx=20, pady=(0, 6))

    format_vars = {}
    _defaults = {"srt", "vtt", "txt_ts"}

    # Descriptions courtes pour chaque format
    _format_desc = {
        "srt":    "Import Premiere Pro, DaVinci, VLC…",
        "vtt":    "YouTube, navigateurs web",
        "txt_ts": "Relecture avec repères temporels",
        "txt":    "Copier-coller simple",
        "json":   "Traitement automatisé, API",
    }

    for key, fmt in EXPORT_FORMATS.items():
        row = tk.Frame(checks_frame, bg=bg)
        row.pack(fill="x", anchor="w")

        var = tk.BooleanVar(value=(key in _defaults))
        format_vars[key] = var

        cb = tk.Checkbutton(
            row, text=fmt["label"], variable=var,
            font=("Segoe UI", 11), fg=fg, bg=bg,
            selectcolor=bg, activebackground=bg, activeforeground=fg,
            anchor="w", padx=4, pady=1,
        )
        cb.pack(side="left")

        desc = _format_desc.get(key, "")
        if desc:
            tk.Label(row, text=f"— {desc}",
                     font=("Segoe UI", 8), fg=fg2, bg=bg).pack(side="left", padx=(2, 0))

    # ── Status label ──
    status_var = tk.StringVar(value="")
    status_lbl = tk.Label(dlg, textvariable=status_var,
                          font=("Segoe UI", 9), fg=COLOR_GREEN, bg=bg,
                          wraplength=300, justify="left")
    status_lbl.pack(fill="x", padx=16, pady=(4, 4))

    # ── Boutons ──
    btn_bar = tk.Frame(dlg, bg=bg)
    btn_bar.pack(fill="x", padx=16, pady=(4, 14))

    # Bouton "Exporter" — pill vert
    _export_done = [False]   # empêche le double-clic

    def _do_export_action(e=None):
        if _export_done[0]:
            return
        selected = [k for k, v in format_vars.items() if v.get()]
        if not selected:
            status_var.set(f"⚠ {tr('export_select_one')}")
            status_lbl.configure(fg=COLOR_RED)
            return
        _export_done[0] = True
        try:
            created = export_files(
                segments, source, selected,
                source_filename=os.path.basename(source),
                output_dir=_dest_dir[0],
            )
            if created:
                status_var.set("✅ " + ", ".join(created))
                status_lbl.configure(fg=COLOR_GREEN)
                log_error(msg=f"[EXPORT] {len(created)} fichier(s) : {', '.join(created)}")
            else:
                status_var.set(f"⚠ {tr('export_no_file')}")
                status_lbl.configure(fg=COLOR_RED)
                _export_done[0] = False
        except Exception as exc:
            log_error(exc, "Export échoué")
            status_var.set(f"❌ {str(exc)[:60]}")
            status_lbl.configure(fg=COLOR_RED)
            _export_done[0] = False

    _create_pill_button(
        btn_bar, 140, PILL_H, tr("export_btn"),
        COLOR_GREEN, COLOR_GREEN_HOVER, bg=bg, tag="go",
        callback=_do_export_action,
        pack_opts={"side": "left", "padx": (0, 10)},
    )

    # Bouton "Fermer" — pill gris
    _create_pill_button(
        btn_bar, 110, PILL_H, tr("export_close"),
        fg2, COLOR_GREY_HOVER, bg=bg, tag="cn",
        callback=lambda e: dlg.destroy(),
        pack_opts={"side": "left"},
    )

    dlg.bind("<Escape>", lambda e: dlg.destroy())

    # ── Drag fenêtre (overrideredirect) ──
    _bind_toplevel_drag(hdr, dlg)

    # Taille, centrage, coins arrondis
    _finalize_toplevel(dlg, 380, 400, min_w=340, min_h=320)


# ── Fenêtre Macros ────────────────────────────────────────────────────────
def process_and_paste(texte: str, delay: float = PASTE_DELAY) -> str:
    """Applique macros + actions + dictionnaire puis colle. Retourne le texte final."""
    texte = apply_macros(texte, config)
    texte = apply_actions(texte, config, set_status=set_statut_safe)
    texte = apply_dictionary(texte, config)
    # Capitaliser la première lettre (Whisper renvoie parfois en minuscule)
    if texte and texte[0].islower():
        texte = texte[0].upper() + texte[1:]
    if texte:
        set_texte_safe(texte)
        copy_and_paste(texte, delay=delay)
    return texte

# -- Phase 4 ui.init() -- copy_and_paste --------------------------------
ui.init(copy_and_paste=copy_and_paste)

# (macros / actions / dictionnaire → core/macros.py)

# _make_scroll_area, _apply_rounded_toplevel, _bind_rounded_toplevel
# -> importes de ui.helpers

# ── Builders d'onglets pour open_macros() ────────────────────────────────

def _build_macros_tab(notebook, win, t):
    """Construit l'onglet Macros texte. Retourne macro_rows."""
    bg  = t["bg"]
    fg2 = t["fg2"]
    vc  = t.get("vu_color", "#22d3ee")
    _ibg = t.get("input_bg", "#2d2d44")
    _ifg = t.get("input_fg", "white")

    tab = tk.Frame(notebook, bg=bg)
    notebook.add(tab, text=f"  {tr('macros_tab')}  ")

    _wrap_w = max(250, int(430 * _SCALE))
    tk.Label(tab, text=tr("macro_help_text"), bg=bg, fg=COLOR_BLUE,
             font=("Consolas", 14), wraplength=_wrap_w).pack(pady=(8, 4))

    _mac_pad = max(8, int(16 * _SCALE))
    fh_m = tk.Frame(tab, bg=bg)
    fh_m.pack(fill="x", padx=_mac_pad)
    tk.Label(fh_m, text=tr("macro_col_name"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left")
    tk.Label(fh_m, text=tr("macro_col_text"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left", padx=(6, 0))

    _btn_add_m = _create_pill_button(
        tab, 150, PILL_H, tr("macro_add"),
        vc, COLOR_RED, bg=bg, emoji="+", text_color=bg,
        font=PILL_FONT_LG, emoji_font=("Segoe UI", 13, "bold"),
        tag="btn_add_m", pack_opts={"pady": (6, 4)},
    )

    cs_m, if_m, _mw_m = _make_scroll_area(tab, bg)

    macro_rows = []
    _entry_w = max(8, int(13 * _SCALE))

    def add_macro_row(name="", text=""):
        row = tk.Frame(if_m, bg=bg)
        row.pack(fill="x", pady=2)
        vn = tk.StringVar(win, value=name)
        vt = tk.StringVar(win, value=text)
        en = tk.Entry(row, textvariable=vn, width=_entry_w,
                      bg=_ibg, fg=_ifg, font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        en.pack(side="left")
        et = tk.Entry(row, textvariable=vt,
                      bg=_ibg, fg=_ifg, font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        et.pack(side="left", fill="x", expand=True, padx=(6, 6))

        def del_m():
            try: macro_rows.remove((vn, vt))
            except ValueError: pass
            row.destroy()

        bd = tk.Button(row, text=tr("macro_delete"), command=del_m,
                       bg=COLOR_RED_DARK, fg="white", relief="flat",
                       font=("Consolas", 14), cursor="hand2", padx=5)
        bd.pack(side="left")
        for w in (row, en, et, bd):
            w.bind("<MouseWheel>", _mw_m)
        macro_rows.append((vn, vt))

    for m in config.get("macros", []):
        add_macro_row(m.get("name", ""), m.get("text", ""))

    def on_add_macro():
        add_macro_row()
        win.after(50, lambda: cs_m.yview_moveto(1.0))

    _btn_add_m.bind("<Button-1>", lambda e: on_add_macro())
    return macro_rows


def _build_actions_tab(notebook, win, t):
    """Construit l'onglet Actions vocales. Retourne (v_action_trigger, action_rows)."""
    bg  = t["bg"]
    fg  = t["fg"]
    fg2 = t["fg2"]
    vc  = t.get("vu_color", "#22d3ee")
    accent = t.get("btn_icon_bg", "#2a2a3e")
    _ibg = t.get("input_bg", "#2d2d44")
    _ifg = t.get("input_fg", "white")

    tab = tk.Frame(notebook, bg=bg)
    notebook.add(tab, text=f"  {tr('actions_tab')}  ")

    _mac_pad = max(8, int(16 * _SCALE))
    _wrap_w  = max(250, int(430 * _SCALE))

    # Mot déclencheur actions
    frame_trig = tk.Frame(tab, bg=bg)
    frame_trig.pack(fill="x", padx=_mac_pad, pady=(10, 2))
    tk.Label(frame_trig, text=tr("action_trigger_label") + " :",
             bg=bg, fg=fg2, font=("Consolas", 16)).pack(side="left")
    v_action_trigger = tk.StringVar(win, value=config.get("action_trigger", "action"))
    tk.Entry(frame_trig, textvariable=v_action_trigger, width=12,
             bg=_ibg, fg=_ifg, font=("Consolas", 16),
             insertbackground=_ifg, relief="flat", bd=4).pack(side="left", padx=6)

    tk.Label(tab, text=tr("action_help"), bg=bg, fg=COLOR_BLUE,
             font=("Consolas", 14), wraplength=_wrap_w).pack(pady=(2, 6))

    # Actions intégrées
    tk.Label(tab, text=tr("action_builtin"), bg=bg, fg=COLOR_PURPLE,
             font=("Consolas", 14, "bold")).pack(anchor="w", padx=_mac_pad)

    frame_builtin = tk.Frame(tab, bg=_ibg, bd=0)
    frame_builtin.pack(fill="x", padx=_mac_pad, pady=(4, 10))

    BUILTIN_DISPLAY = [
        "🗂 explorateur", "💻 bureau", "📊 excel", "📝 word",
        "🧮 calculatrice", "📓 bloc-notes", "🌐 chrome", "🦊 firefox",
        "🌐 edge", "⚙ taches", "🎨 paint",
    ]
    trigger_example = config.get("action_trigger", "action")
    for i, label in enumerate(BUILTIN_DISPLAY):
        col = i % 3
        row_i = i // 3
        cell = tk.Frame(frame_builtin, bg=accent, bd=1, relief="solid")
        cell.grid(row=row_i, column=col, padx=3, pady=3, sticky="ew")
        frame_builtin.grid_columnconfigure(col, weight=1)
        vocal_name = label.split(" ", 1)[1]
        tk.Label(cell, text=label, bg=accent, fg=fg,
                 font=("Consolas", 14, "bold")).pack(anchor="w", padx=6, pady=(4, 0))
        tk.Label(cell, text=tr("action_say_hint", trigger=trigger_example, name=vocal_name),
                 bg=accent, fg=fg2,
                 font=("Consolas", 12)).pack(anchor="w", padx=6, pady=(0, 4))

    # Actions personnalisées
    tk.Label(tab, text=tr("action_custom"), bg=bg, fg=COLOR_GREEN,
             font=("Consolas", 14, "bold")).pack(anchor="w", padx=_mac_pad, pady=(6, 2))

    fh_a = tk.Frame(tab, bg=bg)
    fh_a.pack(fill="x", padx=_mac_pad, pady=(0, 2))
    tk.Label(fh_a, text=tr("action_col_name"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left")
    tk.Label(fh_a, text=tr("action_col_path"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left", padx=(6, 0))

    _btn_add_a = _create_pill_button(
        tab, 180, PILL_H, tr("action_col_add"),
        vc, COLOR_GREEN, bg=bg, emoji="+", text_color=bg,
        font=PILL_FONT_LG, emoji_font=("Segoe UI", 13, "bold"),
        tag="btn_add_a", pad=1, pack_opts={"pady": (2, 4)},
    )

    # Zone scrollable actions perso (custom pour hauteur fixe)
    _fa_scroll_outer = tk.Frame(tab, bg=bg)
    _fa_scroll_outer.pack(fill="x", expand=False, padx=_mac_pad, pady=0)
    cs_a = tk.Canvas(_fa_scroll_outer, bg=bg, highlightthickness=0, height=110)
    _fa_sb = tk.Scrollbar(_fa_scroll_outer, orient="vertical", command=cs_a.yview)
    cs_a.configure(yscrollcommand=_fa_sb.set)
    if_a = tk.Frame(cs_a, bg=bg)
    _fa_win = cs_a.create_window((0, 0), window=if_a, anchor="nw")

    _fa_sb_visible = [False]

    def _fa_on_inner_configure(e):
        cs_a.configure(scrollregion=cs_a.bbox("all"))
        need_sb = if_a.winfo_reqheight() > cs_a.winfo_height()
        if need_sb and not _fa_sb_visible[0]:
            _fa_sb.pack(side="right", fill="y")
            _fa_sb_visible[0] = True
        elif not need_sb and _fa_sb_visible[0]:
            _fa_sb.pack_forget()
            _fa_sb_visible[0] = False

    def _fa_on_canvas_configure(e):
        cs_a.itemconfig(_fa_win, width=e.width)

    if_a.bind("<Configure>", _fa_on_inner_configure)
    cs_a.bind("<Configure>", _fa_on_canvas_configure)
    cs_a.pack(side="left", fill="both", expand=True)

    _mw_a_accum = [0.0]
    def _mw_a(e):
        _mw_a_accum[0] += -e.delta / 120.0
        lines = int(_mw_a_accum[0])
        if lines:
            cs_a.yview_scroll(lines, "units")
            _mw_a_accum[0] -= lines

    action_rows = []
    _entry_w = max(8, int(13 * _SCALE))

    def add_action_row(name="", path=""):
        row = tk.Frame(if_a, bg=bg)
        row.pack(fill="x", pady=2)
        vn = tk.StringVar(win, value=name)
        vp = tk.StringVar(win, value=path)

        en = tk.Entry(row, textvariable=vn, width=_entry_w,
                      bg=_ibg, fg=_ifg, font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        en.pack(side="left")

        ep = tk.Entry(row, textvariable=vp,
                      bg=_ibg, fg=_ifg, font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        ep.pack(side="left", fill="x", expand=True, padx=(6, 4))

        def browse():
            win.attributes("-topmost", False)
            try:
                f = filedialog.askopenfilename(
                    parent=win,
                    title=tr("action_browse_title"),
                    filetypes=[(tr("action_browse_filter"), "*.exe"), (tr("file_all_types"), "*.*")]
                )
            finally:
                win.attributes("-topmost", True)
            if f and isinstance(f, str):
                vp.set(f)

        tk.Button(row, text=tr("action_browse"), command=browse,
                  bg=COLOR_BLUE_DARK, fg="white", relief="flat",
                  font=("Consolas", 14), cursor="hand2", padx=5).pack(side="left")

        def del_a():
            try: action_rows.remove((vn, vp))
            except ValueError: pass
            row.destroy()

        tk.Button(row, text=tr("action_delete"), command=del_a,
                  bg=COLOR_RED_DARK, fg="white", relief="flat",
                  font=("Consolas", 14), cursor="hand2", padx=5).pack(side="left", padx=(2, 0))

        for w in (row, en, ep):
            w.bind("<MouseWheel>", _mw_a)
        action_rows.append((vn, vp))

    for a in config.get("actions", []):
        add_action_row(a.get("name", ""), a.get("path", ""))

    def on_add_action():
        add_action_row()
        win.after(50, lambda: cs_a.yview_moveto(1.0))

    _btn_add_a.bind("<Button-1>", lambda e: on_add_action())
    return v_action_trigger, action_rows


def _build_dict_tab(notebook, win, t):
    """Construit l'onglet Dictionnaire. Retourne dict_rows."""
    bg  = t["bg"]
    fg2 = t["fg2"]
    vc  = t.get("vu_color", "#22d3ee")
    accent = t.get("btn_icon_bg", "#2a2a3e")
    _ibg = t.get("input_bg", "#2d2d44")
    _ifg = t.get("input_fg", "white")

    tab = tk.Frame(notebook, bg=bg)
    notebook.add(tab, text=f"  {tr('dict_tab')}  ")

    _mac_pad = max(8, int(16 * _SCALE))
    _wrap_w  = max(250, int(430 * _SCALE))

    tk.Label(tab, text=tr("dict_help"), bg=bg, fg=COLOR_BLUE,
             font=("Consolas", 14), wraplength=_wrap_w).pack(pady=(10, 2))
    tk.Label(tab, text=tr("dict_example"), bg=bg, fg=fg2,
             font=("Consolas", 14), wraplength=_wrap_w).pack(pady=(0, 6))

    fh_d = tk.Frame(tab, bg=bg)
    fh_d.pack(fill="x", padx=_mac_pad)
    tk.Label(fh_d, text=tr("dict_wrong"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left")
    tk.Label(fh_d, text="→", bg=bg, fg=COLOR_ORANGE,
             font=("Consolas", 16, "bold")).pack(side="left", padx=(4, 4))
    tk.Label(fh_d, text=tr("dict_correct"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left")

    _btn_add_d = _create_pill_button(
        tab, 180, PILL_H, tr("dict_col_add"),
        vc, COLOR_RED, bg=bg, emoji="+", text_color=bg,
        font=PILL_FONT_LG, emoji_font=("Segoe UI", 13, "bold"),
        tag="btn_add_d", pad=1, pack_opts={"pady": (6, 4)},
    )

    cs_d, if_d, _mw_d = _make_scroll_area(tab, bg)

    dict_rows = []

    def add_dict_row(wrong="", correct=""):
        _row_even_bg = _ibg
        _row_odd_bg  = accent
        row_bg = _row_even_bg if len(dict_rows) % 2 == 0 else _row_odd_bg

        row = tk.Frame(if_d, bg=row_bg)
        row.pack(fill="x", pady=1)
        vw    = tk.StringVar(win, value=wrong)
        v_cor = tk.StringVar(win, value=correct)

        _dict_w = max(10, int(20 * _SCALE))
        ew = tk.Entry(row, textvariable=vw, width=_dict_w,
                      bg=_ibg, fg="#ff9966", font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        ew.pack(side="left", padx=(6, 0), pady=4)

        tk.Label(row, text="→", bg=row_bg, fg=COLOR_ORANGE,
                 font=("Consolas", 10, "bold")).pack(side="left", padx=(4, 4))

        def del_d():
            try: dict_rows.remove((vw, v_cor))
            except ValueError: pass
            row.destroy()

        bd = tk.Button(row, text=tr("dict_delete"), command=del_d,
                       bg=COLOR_RED_DARK, fg="white", relief="flat",
                       font=("Consolas", 14), cursor="hand2", padx=5)
        bd.pack(side="right", padx=(0, 6), pady=4)

        ec = tk.Entry(row, textvariable=v_cor,
                      bg=_ibg, fg=COLOR_GREEN, font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        ec.pack(side="left", fill="x", expand=True, padx=(0, 4), pady=4)

        for w in (row, ew, ec, bd):
            w.bind("<MouseWheel>", _mw_d)
        dict_rows.append((vw, v_cor))

    for d in config.get("dictionary", []):
        add_dict_row(d.get("wrong", ""), d.get("correct", ""))

    def on_add_dict():
        add_dict_row()
        win.after(50, lambda: cs_d.yview_moveto(1.0))

    _btn_add_d.bind("<Button-1>", lambda e: on_add_dict())
    return dict_rows


def open_macros() -> None:
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
        try:
            if hasattr(win, '_rounded_job') and win._rounded_job:
                win.after_cancel(win._rounded_job)
            win.destroy()
        except tk.TclError:
            pass
    win.protocol("WM_DELETE_WINDOW", on_close_macros)

    # ── Header personnalisé (drag + titre + ✕) ────────────────────────────
    _mac_hdr_pad = max(8, int(14 * _SCALE))
    frame_hdr = tk.Frame(win, bg=bg)
    frame_hdr.pack(fill="x", padx=_mac_hdr_pad, pady=(12, 0))

    tk.Label(frame_hdr, text=tr("macro_title"), bg=bg,
             fg=t.get("fg_title", fg), font=("Segoe UI", 16, "bold")).pack(side="left", expand=True)

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

    _bind_toplevel_drag(frame_hdr, win)

    # Séparateur cyan (accent) sous la barre de titre
    tk.Frame(win, height=1, bg=t.get("vu_color", "#22d3ee")).pack(fill="x", padx=_mac_hdr_pad, pady=(8, 0))

    # ── Notebook (onglets) ─────────────────────────────────────────────────
    _nb_style = ttk.Style(win)
    _nb_style.theme_use("default")
    _nb_style.configure("Helio.TNotebook",     background=bg, borderwidth=0)
    _nb_style.configure("Helio.TNotebook.Tab",
                    background=accent, foreground=fg2,
                    font=("Segoe UI", 14, "bold"),
                    padding=[14, 7])
    _nb_style.map("Helio.TNotebook.Tab",
              background=[("selected", vc)],
              foreground=[("selected", bg)])

    # ── Footer fixe (AVANT notebook dans le pack pour être toujours visible) ─
    # On le place ici mais avec side="bottom" → il sera rendu en dernier
    # mais réservé en premier dans l'espace disponible
    footer_frame = tk.Frame(win, bg=bg)
    footer_frame.pack(side="bottom", fill="x", padx=_mac_hdr_pad, pady=(4, 14))

    tk.Frame(footer_frame, height=1, bg=fg2).pack(fill="x", pady=(0, 8))

    _btn_save = _create_pill_button(
        footer_frame, 200, PILL_H_LG, tr("save_button"),
        COLOR_SAVE, COLOR_SAVE_HOVER, bg=bg,
        emoji="💾", font=PILL_FONT_LG, tag="bs",
    )
    # bind save_all défini plus bas — on le connecte après

    notebook = ttk.Notebook(win, style="Helio.TNotebook")
    notebook.pack(fill="both", expand=True, padx=max(6, int(12 * _SCALE)), pady=(8, 0))

    # Construction des 3 onglets
    macro_rows = _build_macros_tab(notebook, win, t)
    v_action_trigger, action_rows = _build_actions_tab(notebook, win, t)
    dict_rows = _build_dict_tab(notebook, win, t)

    # ═══════════════════════════════════════════════════════════════════════
    # Bouton Sauvegarder (commun aux trois onglets)
    # ═══════════════════════════════════════════════════════════════════════
    def save_all():
        # Limites de longueur — prévient regex DoS et config géante
        _MAX_NAME = 200
        _MAX_TEXT = 10000     # texte de remplacement max (macros/dictionnaire)
        _MAX_ENTRIES = 500    # nombre max d'entrées par catégorie
        # Sauvegarder macros texte (le nom est le déclencheur direct)
        config["macros"] = [
            {"name": vn.get().strip()[:_MAX_NAME], "text": vt.get()[:_MAX_TEXT]}
            for vn, vt in macro_rows
            if vn.get().strip()
        ]
        # Sauvegarder actions
        config["action_trigger"] = (v_action_trigger.get().strip().replace(" ", "")[:_MAX_NAME]) or "action"
        config["actions"] = [
            {"name": vn.get().strip().replace(" ", "_")[:_MAX_NAME], "path": vp.get().strip()}
            for vn, vp in action_rows
            if vn.get().strip() and vp.get().strip()
        ]
        # Sauvegarder dictionnaire
        config["dictionary"] = [
            {"wrong": vw.get().strip()[:_MAX_NAME], "correct": v_cor.get()[:_MAX_TEXT]}
            for vw, v_cor in dict_rows
            if vw.get().strip()
        ]
        # Limiter le nombre d'entrées pour éviter les ralentissements
        for _key in ("macros", "actions", "dictionary"):
            if len(config.get(_key, [])) > _MAX_ENTRIES:
                config[_key] = config[_key][:_MAX_ENTRIES]
        save_config(config)   # save_config appelle déjà invalidate_regex_cache()
        on_close_macros()     # cancel _rounded_job + destroy (pas de race condition)

    # Connecter le bouton save (défini plus haut) à save_all
    _btn_save.bind("<Button-1>", lambda e: save_all())

    # Taille, centrage, coins arrondis
    _finalize_toplevel(win, 700, 820, min_h=400)


# ── Audio avec Ring Buffer ────────────────────────────────────────────────
# Buffer pour MAX_RECORD_SECONDS
audio_buffer = RingBuffer(SAMPLE_RATE * MAX_RECORD_SECONDS)
is_recording = threading.Event()

# Pré-buffer : capture en permanence les dernières ~0.5s d'audio
# Quand l'enregistrement démarre, ces données sont injectées dans le buffer
# → plus de perte des premiers mots lors de l'appui sur le bouton
_PRE_BUFFER_BLOCKS = 3  # 3 × 4096 = 12288 samples = ~0.77s à 16 kHz
_pre_buffer = deque(maxlen=_PRE_BUFFER_BLOCKS)

_stream_error = threading.Event()   # set() si le stream audio a signalé une erreur

def audio_callback(indata, frames, time_info, status):
    """Callback audio avec gestion d'erreur."""
    try:
        if status:
            _stream_error.set()
        if is_recording.is_set():
            audio_buffer.append(indata)
            # RMS via np.dot (zéro allocation numpy intermédiaire)
            flat = indata.ravel()
            if flat.size > 0:
                rms = (np.dot(flat, flat) / flat.size) ** 0.5
            else:
                rms = 0.0
            v = float(rms) * VU_RMS_GAIN
            vu_level[0] = min(1.0, v) if v == v else 0.0  # NaN != NaN
        else:
            _pre_buffer.append(indata.copy())  # garder les dernières ~0.5s
            vu_level[0] = 0.0
    except Exception as e:
        log_error(e, "Erreur callback audio")

# ── Micro à 100% — meilleure transcription ──────────────────────────────
def _set_mic_volume_100():
    """Met le micro Windows par défaut à 100% via pycaw (Windows Core Audio API)."""
    def _do_pycaw():
        """Sous-fonction pour scoper les variables COM locales."""
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        mic = AudioUtilities.GetMicrophone()
        if not mic:
            return "[MIC] Aucun microphone trouvé"
        interface = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(interface, POINTER(IAudioEndpointVolume))
        before = vol.GetMasterVolumeLevelScalar()
        if before < 0.99:
            vol.SetMasterVolumeLevelScalar(1.0, None)
            return f"[MIC] Volume micro {before*100:.0f}% → 100%"
        return "[MIC] Volume micro déjà à 100%"

    def _do():
        import comtypes
        comtypes.CoInitialize()
        msg = "[MIC] Erreur inconnue"
        try:
            msg = _do_pycaw()
        except Exception as e:
            msg = f"Échec mise à 100% du volume micro: {e}"
        finally:
            # Forcer GC des objets COM dans CE thread (apartment correct)
            gc.collect()
            gc.collect()
            # Neutraliser __del__ de comtypes pour empêcher crash GC cross-thread
            try:
                from comtypes._post_coinit import unknwn
                unknwn._compointer_base.__del__ = lambda self: None
            except Exception:
                pass
            comtypes.CoUninitialize()
        log_error(msg=msg)
    threading.Thread(target=_do, daemon=True).start()

_set_mic_volume_100()

# Initialiser le stream audio
try:
    stream[0] = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32',
                                callback=audio_callback, blocksize=AUDIO_BLOCKSIZE)
    stream[0].start()
except sd.PortAudioError as e:
    log_error(e, "Aucun microphone détecté")
    stream[0] = None

# ── Streaming temps réel (modèle tiny en parallèle) ──────────────────────
_streamer = StreamingTranscriber(
    language=config["language"],
    device="cpu",     # tiny toujours sur CPU — ne pas concurrencer le GPU principal
    on_log=lambda msg: log_error(msg=msg),
)
_streamer.enabled = config.get("streaming", True)

# Label flottant pour l'aperçu streaming (Toplevel overrideredirect)
_streaming_label_win = [None]     # Toplevel ou None
_streaming_label_text = [None]    # tk.Label à l'intérieur
_streaming_job = [None]           # after() id pour le polling position curseur

_STREAMING_INTERVAL_MS = 1500     # Transcrire toutes les 1.5 secondes
_STREAMING_LABEL_OFFSET_Y = 35    # Pixels sous le curseur


def _show_streaming_label(text):
    """Affiche ou met à jour le label flottant d'aperçu streaming."""
    if not text or not _streamer.enabled:
        _hide_streaming_label()
        return

    try:
        if _streaming_label_win[0] is None or not _streaming_label_win[0].winfo_exists():
            w = tk.Toplevel(root)
            w.withdraw()
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            w.attributes("-alpha", 0.85)
            w.configure(bg="#1a1a2e")
            lbl = tk.Label(
                w, text=text,
                bg="#1a1a2e", fg="#e0e0e0",
                font=("Segoe UI", 20),
                wraplength=800,
                padx=12, pady=6,
                justify="left",
            )
            lbl.pack()
            _streaming_label_win[0] = w
            _streaming_label_text[0] = lbl
            w.deiconify()
        else:
            _streaming_label_text[0].config(text=text)

        # Positionner sous le curseur (clampé aux bords de l'écran)
        try:
            w = _streaming_label_win[0]
            mx = root.winfo_pointerx()
            my = root.winfo_pointery()
            if mx >= 0 and my >= 0:
                w.update_idletasks()
                lbl_w = w.winfo_reqwidth()
                lbl_h = w.winfo_reqheight()
                sw = root.winfo_screenwidth()
                sh = root.winfo_screenheight()
                x_pos = min(mx, sw - lbl_w - 10)
                y_pos = my + _STREAMING_LABEL_OFFSET_Y
                if y_pos + lbl_h > sh - 10:
                    y_pos = my - lbl_h - 10  # au-dessus du curseur si en bas
                w.geometry(f"+{x_pos}+{y_pos}")
        except Exception:
            pass
    except Exception as e:
        log_error(e, "streaming label")


def _hide_streaming_label():
    """Cache et détruit le label flottant."""
    try:
        if _streaming_label_win[0] is not None:
            _streaming_label_win[0].destroy()
    except Exception:
        pass
    _streaming_label_win[0] = None
    _streaming_label_text[0] = None


def _update_streaming_label_position():
    """Met à jour la position du label pour suivre le curseur."""
    if _streaming_label_win[0] is not None:
        try:
            w = _streaming_label_win[0]
            if w.winfo_exists():
                mx = root.winfo_pointerx()
                my = root.winfo_pointery()
                if mx >= 0 and my >= 0:
                    lbl_w = w.winfo_reqwidth()
                    lbl_h = w.winfo_reqheight()
                    sw = root.winfo_screenwidth()
                    sh = root.winfo_screenheight()
                    x_pos = min(mx, sw - lbl_w - 10)
                    y_pos = my + _STREAMING_LABEL_OFFSET_Y
                    if y_pos + lbl_h > sh - 10:
                        y_pos = my - lbl_h - 10
                    w.geometry(f"+{x_pos}+{y_pos}")
        except Exception:
            pass
    # Re-planifier tant qu'on enregistre
    if is_recording.is_set() and _streamer.enabled:
        _streaming_job[0] = root.after(50, _update_streaming_label_position)


# (clavier / hotkeys → core/hotkeys.py)


# (transcription + copier-coller → core/transcription.py)

def transcribe_audio(model, audio_data, use_vad=True):
    """Wrapper : transcrit via core/transcription.py avec les globals."""
    return _transcribe_audio_core(
        model, audio_data, config,
        device=detected_device, compute=detected_compute, use_vad=use_vad,
    )

def copy_and_paste(text: str, delay: float = PASTE_DELAY) -> None:
    """Wrapper : copie-colle via core/transcription.py avec les globals."""
    _copy_and_paste_core(
        text, delay=delay,
        restore_focus_fn=_restore_target_focus,
        target_hwnd=_target_hwnd[0],
    )

# ── Chargement & boucle principale ────────────────────────────────────────
_global_model = [None]   # modèle Whisper persisté — évite rechargement par watchdog

def _load_model() -> None:
    """Wrapper : charge le modèle via core/model.py et met à jour les globals."""
    global detected_device, detected_compute
    model, detected_device, detected_compute = _load_model_core(
        config, detected_device, detected_compute,
        on_status=lambda txt: set_statut_safe(txt, COLOR_ORANGE, COLOR_ORANGE),
    )
    return model


def _recover_stream_error():
    """Détecte et récupère les erreurs de stream audio (micro déconnecté)."""
    if not _stream_error.is_set():
        return
    _stream_error.clear()
    log_error(msg="Erreur stream audio détectée (micro déconnecté ?)")
    set_statut_safe(tr("mic_error"), COLOR_RED, COLOR_RED)
    try:
        if stream[0]:
            stream[0].abort()
            stream[0].close()
    except Exception:
        pass
    # Retry avec backoff (1s, 2s, 3s) au lieu d'un sleep fixe 2s
    for _attempt in range(3):
        if _app_closing[0]:
            return
        time.sleep(1 + _attempt)
        try:
            new_stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1,
                dtype='float32', callback=audio_callback,
                blocksize=AUDIO_BLOCKSIZE)
            new_stream.start()
            stream[0] = new_stream
            set_statut_safe(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)
            return
        except Exception as e_restart:
            log_error(e_restart, f"Relance audio tentative {_attempt + 1}/3")
    stream[0] = None
    set_statut_safe(tr("mic_error"), COLOR_RED, COLOR_RED)


def _record_meeting_loop(model):
    """Boucle d'enregistrement en mode réunion — segmente et transcrit automatiquement."""
    MAX_TICKS   = int(MEETING_MAX_DURATION / MEETING_POLL)
    GRACE_TICKS = int(MEETING_GRACE_PERIOD / MEETING_POLL)

    while mode_libre[0] and not _app_closing[0]:
        silence_time    = 0.0
        voice_time      = 0.0
        elapsed_ticks   = 0
        last_voice_seen = False
        in_grace        = False
        _capture_target_window()

        # Boucle interne : accumulation voix/silence pour un segment
        while mode_libre[0] and not _app_closing[0]:
            time.sleep(MEETING_POLL)
            elapsed_ticks += 1
            chunk_size = int(SAMPLE_RATE * 0.15)
            recent_chunk = audio_buffer.get_tail(chunk_size)
            voice_now = has_voice(recent_chunk)
            if voice_now:
                silence_time    = 0.0
                last_voice_seen = True
                voice_time     += MEETING_POLL
            else:
                if last_voice_seen:
                    silence_time += MEETING_POLL
            enough_voice   = voice_time >= MEETING_MIN_VOICE_DURATION
            enough_silence = silence_time >= MEETING_SILENCE_THRESHOLD
            if last_voice_seen and enough_silence and enough_voice:
                break
            if elapsed_ticks >= MAX_TICKS and not in_grace:
                in_grace = True
            if in_grace:
                if silence_time >= MEETING_GRACE_SILENCE:
                    break
                if elapsed_ticks >= MAX_TICKS + GRACE_TICKS:
                    break

        if _app_closing[0]:
            break

        audio = audio_buffer.get_data()
        if mode_libre[0] and not _app_closing[0]:
            audio_buffer.clear()    # clear D'ABORD (l'ancien segment est dans `audio`)
            is_recording.set()      # PUIS activer → le callback écrit dans un buffer propre
            set_statut_safe(tr("meeting_on"), COLOR_RED, COLOR_RED)
        else:
            is_recording.clear()

        if audio.size > 0 and last_voice_seen:
            set_statut_safe(tr("transcribing"), COLOR_ORANGE, COLOR_ORANGE)
            texte = transcribe_audio(model, audio)
            if texte:
                process_and_paste(texte)
            if not mode_libre[0]:
                audio_buffer.clear()

    # Transcription finale du mode réunion
    if not _app_closing[0]:
        audio = audio_buffer.get_data()
        is_recording.clear()
        if audio.size > 0:
            set_statut_safe(tr("final_trans"), COLOR_ORANGE, COLOR_ORANGE)
            texte = transcribe_audio(model, audio)
            if texte:
                process_and_paste(texte, delay=0.3)


def _record_ptt(model, hotkey):
    """Enregistre et transcrit un segment push-to-talk.

    Si le streaming est activé, transcrit périodiquement avec le modèle tiny
    et affiche un aperçu dans un label flottant sous le curseur.
    La transcription finale (au relâchement) utilise toujours le modèle principal.
    """
    _hold_start = time.perf_counter()
    _last_stream_time = time.perf_counter()
    _streaming_active = _streamer.enabled and _streamer.is_ready

    # Démarrer le suivi du curseur pour le label flottant
    if _streaming_active:
        _streamer.reset()
        _safe_after(0, _update_streaming_label_position)

    while is_hotkey_pressed(hotkey) and not _app_closing[0]:
        # ── Streaming périodique : transcrire un aperçu toutes les ~1.5s ──
        if _streaming_active:
            _now = time.perf_counter()
            if (_now - _last_stream_time) >= (_STREAMING_INTERVAL_MS / 1000.0):
                _last_stream_time = _now
                _audio_snap = audio_buffer.get_data()
                if _audio_snap.size > 0:
                    _preview = _streamer.transcribe_chunk(_audio_snap)
                    if _preview:
                        _safe_after(0, lambda t=_preview: _show_streaming_label(t))
        time.sleep(POLL_INTERVAL)

    # ── Cacher le label streaming dès le relâchement ──
    if _streaming_active:
        _safe_after(0, _hide_streaming_label)

    if not _app_closing[0]:
        _hold_ms = (time.perf_counter() - _hold_start) * 1000
        audio = audio_buffer.get_data()
        is_recording.clear()
        # Clic trop court (< 300ms) → accidentel, pas de parole
        if _hold_ms < 300:
            log_error(msg=f"[SKIP] Clic trop court: {_hold_ms:.0f}ms (min=300ms)")
            audio_buffer.clear()
            set_statut_safe(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)
            time.sleep(DEBOUNCE_DELAY)
            return
        set_statut_safe(tr("transcribing"), COLOR_ORANGE, COLOR_ORANGE)
        if audio.size > 0:
            texte = transcribe_audio(model, audio)
            if texte:
                process_and_paste(texte)
            else:
                log_error(msg=f"[SKIP] Transcription vide pour {audio.size/SAMPLE_RATE:.1f}s audio")
        audio_buffer.clear()
        time.sleep(DEBOUNCE_DELAY)


def chargement() -> None:
    """Thread principal de chargement et transcription."""
    global detected_device, detected_compute, hw_info

    # Détection GPU (déplacée ici pour accélérer le démarrage de ~0.5s)
    if detected_device == "auto":
        try:
            detected_device, detected_compute, hw_info = init_device()
        except Exception as e:
            log_error(e, "init_device échoué — fallback CPU")
            detected_device, detected_compute = "cpu", "int8"
            hw_info = "CPU (détection échouée)"
        # Mettre à jour le label hardware dans l'UI
        try:
            _safe_after(0, lambda: hw_label.config(text=hw_info))
        except Exception:
            pass

    if stream[0] is None:
        set_statut_safe(tr("no_mic"), COLOR_RED, COLOR_RED)
        return

    if config["device"] != "auto":
        detected_device, detected_compute = (
            (config["device"], "float16") if config["device"] == "cuda"
            else (config["device"], "int8")
        )

    model = _global_model[0]
    if model is not None:
        set_statut_safe(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)
        set_texte_safe("")
    else:
        set_statut_safe(tr("loading_long"), COLOR_ORANGE, COLOR_ORANGE)

    if model is None:
        model = _load_model()
        if model is None:
            set_statut_safe(tr("model_error"), COLOR_RED, COLOR_RED)
            return
        _global_model[0] = model

    # ── Charger le modèle streaming tiny en arrière-plan ──
    if _streamer.enabled:
        _streamer.set_language(config["language"])
        _streamer.load_async()
        log_error(msg="[STREAMING] Chargement du modèle tiny en arrière-plan...")

    # Afficher le device effectif dans le premier statut "Prêt" (diagnostic perf)
    _dev_tag = "GPU" if detected_device == "cuda" else "CPU"
    _ready_msg = f"{tr('ready', hotkey=_hotkey_label())} ({_dev_tag} {detected_compute})"
    set_statut_safe(_ready_msg, COLOR_GREEN, COLOR_GREEN)
    log_error(msg=f"[PERF] Modèle {config['model']} chargé sur {detected_device}/{detected_compute}")
    set_texte_safe("")

    while not _app_closing[0]:
        try:
            _recover_stream_error()

            hotkey = config["hotkey"]
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
            if hotkey_pressed:
                # Anti-rebond : confirmer que le bouton est encore pressé après 30ms
                # (élimine les faux déclenchements par bounce des boutons souris)
                if hotkey.startswith("mouse_"):
                    time.sleep(0.03)
                    if not is_hotkey_pressed(hotkey):
                        continue  # bounce — ignorer
                _capture_target_window()

            if not _recording_lock.acquire(blocking=False):
                log_error(msg="[SKIP] Lock occupé — enregistrement précédent en cours")
                time.sleep(POLL_INTERVAL)
                continue

            try:
                # Démarrer l'enregistrement IMMÉDIATEMENT — GUI après
                audio_buffer.clear()
                # Injecter le pré-buffer — UNIQUEMENT les blocs avec de la voix
                # (après inactivité, le pré-buffer contient du silence → on l'écarte)
                for _chunk in _pre_buffer:
                    _flat = _chunk.ravel()
                    _rms = (np.dot(_flat, _flat) / _flat.size) ** 0.5
                    if _rms > VAD_THRESHOLD:
                        audio_buffer.append(_chunk)
                _pre_buffer.clear()
                is_recording.set()
                set_statut_safe(tr("recording"), COLOR_RED, COLOR_RED)
                set_texte_safe("")

                if mode_libre[0]:
                    _record_meeting_loop(model)
                else:
                    _record_ptt(model, hotkey)
            finally:
                is_recording.clear()
                try:
                    _recording_lock.release()
                except RuntimeError:
                    pass

            if _app_closing[0]:
                break
            set_statut_safe(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)

        except Exception as e:
            log_error(e)
            if not _app_closing[0]:
                set_statut_safe(tr("ready", hotkey=_hotkey_label()), COLOR_GREEN, COLOR_GREEN)
            time.sleep(0.5)

# ── Watchdog ──────────────────────────────────────────────────────────────
# Pré-cacher le HWND 500ms après démarrage (overrideredirect stabilisé)
root.after(500, _get_root_hwnd)
root.after(200, _setup_drag_drop)      # drag-and-drop fichiers audio

main_thread[0] = threading.Thread(target=chargement, daemon=True)
main_thread[0].start()

def watchdog():
    """Surveille le thread principal et le relance si nécessaire."""
    _restarts = 0
    _MAX_RESTARTS = 5
    _last_restart = 0.0   # monotonic() du dernier restart
    while not _app_closing[0]:
        time.sleep(5)
        # Si le thread tourne depuis >60s après un restart, remettre le compteur à 0
        if _restarts > 0 and _last_restart and time.monotonic() - _last_restart > 60:
            _restarts = 0
        if not _app_closing[0] and main_thread[0] and not main_thread[0].is_alive():
            _restarts += 1
            _last_restart = time.monotonic()
            if _restarts > _MAX_RESTARTS:
                log_error(msg=f"Thread mort {_restarts}x — abandon (max {_MAX_RESTARTS})")
                set_statut_safe(tr("model_error"), COLOR_RED, COLOR_RED)
                break
            log_error(msg=f"Thread mort — relance automatique ({_restarts}/{_MAX_RESTARTS})")
            # Libérer _recording_lock si le thread mort l'avait gardé verrouillé
            # (sinon le nouveau thread serait bloqué indéfiniment sur acquire)
            is_recording.clear()
            try:
                _recording_lock.release()
            except RuntimeError:
                pass   # déjà libéré — normal
            # S'assurer que l'ancien thread est bien mort avant de relancer
            # (évite plusieurs threads chargeant le modèle en parallèle)
            old = main_thread[0]
            if old is not None:
                old.join(timeout=5)
                if old.is_alive():
                    log_error(msg="[WATCHDOG] Ancien thread toujours vivant après join(5s) — skip relance")
                    continue
            main_thread[0] = threading.Thread(target=chargement, daemon=True)
            main_thread[0].start()

threading.Thread(target=watchdog, daemon=True).start()

# ── Nettoyage VRAM (fix crash CUDA) — lancé une seule fois ───────────────
def vram_cleanup():
    """Nettoie la VRAM GPU toutes les 5 minutes pour éviter cudaErrorLaunchFailure.
    Fonctionne avec ou sans torch (gc.collect libère les objets ctranslate2).
    IMPORTANT : gc.collect() est acquis sous _recording_lock pour éviter qu'il
    ne tourne PENDANT une inférence CUDA (cause de Fatal Python error: Aborted).
    """
    _has_torch = False
    try:
        import torch
        _has_torch = torch.cuda.is_available()
    except Exception:
        pass

    while not _app_closing[0]:
        time.sleep(300)  # 5 minutes
        if detected_device != "cuda":
            continue   # device a peut-être basculé CPU (fallback) → skip
        # Acquérir le verrou transcription → évite gc.collect pendant l'inférence
        # (gc.collect ignore gc.disable() et peut corrompre l'état CUDA)
        if not _recording_lock.acquire(timeout=2):
            continue   # dictée en cours — on réessaie dans 5 min
        try:
            # Vérifier APRÈS acquisition du lock (évite TOCTOU race)
            if not _file_transcribing.acquire(blocking=False):
                continue   # transcription fichier en cours — skip
            try:
                gc.collect()   # libère les objets CUDA orphelins (fonctionne toujours)
                if _has_torch:
                    torch.cuda.empty_cache()
            finally:
                _file_transcribing.release()
        except Exception:
            pass
        finally:
            try:
                _recording_lock.release()
            except RuntimeError:
                pass

threading.Thread(target=vram_cleanup, daemon=True).start()

# ── Filet de sécurité — log les sorties inattendues ──────────────────────
def _atexit_guard():
    """Loggue si le processus se termine sans passer par on_close()."""
    if not _app_closing[0]:
        log_error(msg="SORTIE INATTENDUE — le processus a été tué sans on_close()")
atexit.register(_atexit_guard)

# ── Démarrage ─────────────────────────────────────────────────────────────
try:
    root.mainloop()
except Exception as _ml_err:
    log_error(_ml_err, "CRASH mainloop Tkinter")
    if not _app_closing[0]:
        os._exit(1)
