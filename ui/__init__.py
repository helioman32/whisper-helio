"""
Shared UI context for Whisper Hélio v1.5.

Constants (colors, pill dimensions) are defined here as the single source
of truth.  All mutable references are set by dictee.pyw via init() after
root creation.  UI submodules access them via ``import ui`` (late binding).
"""
from __future__ import annotations

# ── Color constants ──────────────────────────────────────────────────────
COLOR_GREEN       = "#2ecc71"
COLOR_GREEN_HOVER = "#27ae60"
COLOR_RED         = "#e74c3c"
COLOR_RED_DARK    = "#c0392b"
COLOR_ORANGE      = "#f39c12"
COLOR_PURPLE      = "#7c3aed"
COLOR_BLUE        = "#3498db"
COLOR_BLUE_DARK   = "#2980b9"
COLOR_WHITE       = "white"
COLOR_SAVE        = "#2563eb"
COLOR_SAVE_HOVER  = "#1d4ed8"
COLOR_GREY_HOVER  = "#555555"

# ── Pill button dimensions / fonts ───────────────────────────────────────
PILL_H         = 34
PILL_H_LG      = 36
PILL_FONT      = ("Segoe UI", 11, "bold")
PILL_FONT_LG   = ("Segoe UI", 14, "bold")
PILL_EMOJI_FONT = ("Segoe UI", 10)

# ── Window constants ─────────────────────────────────────────────────────
CORNER_RADIUS  = 18

# ── References set by dictee.pyw via init() ──────────────────────────────
root = None                # tk.Tk instance
config: dict | None = None
theme = None               # callable → dict
tr = None                  # callable(key, **kw) → str
log_error = None           # callable(e=None, msg=None)
set_statut_safe = None     # callable(text, color, voyant_color)
set_texte_safe = None      # callable(text)
_safe_after = None         # callable(delay_ms, callback)
save_config = None         # callable(config)
fit_window = None          # callable(w, h, sw, sh) → (w, h)
copy_and_paste = None      # callable(text, delay)
apply_theme = None         # callable()
_clear_tr_cache = None     # callable()
_hotkey_label = None        # callable → str

_SCALE: float = 1.0

# ── Mutable state refs (shared with dictee.pyw via init) ─────────────────
_app_closing = None        # [False] list ref
_help_window = None        # [None] list ref
_settings_window = None    # [None] list ref
_macros_window = None      # [None] list ref
_file_transcribe_window = None
_current_theme = None      # [None] list ref (theme cache)

# ── WinAPI handle — set by ui.winapi after ctypes setup ──────────────────
_u32 = None


def init(**kw):
    """Set shared UI references.  Called once from dictee.pyw."""
    g = globals()
    for k, v in kw.items():
        g[k] = v
