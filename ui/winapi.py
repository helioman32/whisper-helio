"""
WinAPI layer — ctypes setup, window management, focus, rounded corners.

Functions access the shared ``root`` via ``ui.root`` (late binding).
Mutable state uses the [value] list pattern for thread-safety.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import time

import ui  # late-binding for root, log_error, etc.

# ─────────────────────────────────────────────────────────────────────────
# ctypes argtypes / restypes (64-bit safe)
# ─────────────────────────────────────────────────────────────────────────

_u32 = ctypes.windll.user32

# SendMessageW — LPARAM est 64 bits
_u32.SendMessageW.argtypes = [ctypes.wintypes.HWND, ctypes.c_uint,
                              ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
_u32.SendMessageW.restype  = ctypes.wintypes.LPARAM

# LoadImageW — HANDLE est 64 bits
_u32.LoadImageW.argtypes = [ctypes.wintypes.HINSTANCE, ctypes.wintypes.LPCWSTR,
                            ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
_u32.LoadImageW.restype  = ctypes.wintypes.HANDLE

# Autres argtypes 64 bits
_u32.GetParent.argtypes            = [ctypes.wintypes.HWND]
_u32.GetParent.restype             = ctypes.wintypes.HWND
_u32.GetForegroundWindow.argtypes  = []
_u32.GetForegroundWindow.restype   = ctypes.wintypes.HWND
_u32.IsWindow.argtypes             = [ctypes.wintypes.HWND]
_u32.IsWindow.restype              = ctypes.wintypes.BOOL
_u32.SetForegroundWindow.argtypes  = [ctypes.wintypes.HWND]
_u32.SetForegroundWindow.restype   = ctypes.wintypes.BOOL
_u32.BringWindowToTop.argtypes     = [ctypes.wintypes.HWND]
_u32.BringWindowToTop.restype      = ctypes.wintypes.BOOL
_u32.AttachThreadInput.argtypes    = [ctypes.wintypes.DWORD, ctypes.wintypes.DWORD, ctypes.wintypes.BOOL]
_u32.AttachThreadInput.restype     = ctypes.wintypes.BOOL
_u32.GetWindowThreadProcessId.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.DWORD)]
_u32.GetWindowThreadProcessId.restype  = ctypes.wintypes.DWORD
_u32.GetWindowLongPtrW.argtypes    = [ctypes.wintypes.HWND, ctypes.c_int]
_u32.GetWindowLongPtrW.restype     = ctypes.c_ssize_t
_u32.SetWindowLongPtrW.argtypes    = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_u32.SetWindowLongPtrW.restype     = ctypes.c_ssize_t
_u32.DestroyIcon.argtypes          = [ctypes.wintypes.HICON]
_u32.DestroyIcon.restype           = ctypes.wintypes.BOOL
_u32.SetWindowRgn.argtypes         = [ctypes.wintypes.HWND, ctypes.c_void_p, ctypes.wintypes.BOOL]
_u32.SetWindowRgn.restype          = ctypes.c_int
ctypes.windll.gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
ctypes.windll.gdi32.CreateRoundRectRgn.restype  = ctypes.c_void_p
ctypes.windll.gdi32.DeleteObject.argtypes       = [ctypes.c_void_p]
ctypes.windll.gdi32.DeleteObject.restype        = ctypes.wintypes.BOOL

# Export _u32 to ui context for helpers.py
ui._u32 = _u32


# ─────────────────────────────────────────────────────────────────────────
# WinAPI constants
# ─────────────────────────────────────────────────────────────────────────

GWL_EXSTYLE      = -20
WS_EX_APPWINDOW  = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WM_SETICON       = 0x0080
ICON_SMALL       = 0
ICON_BIG         = 1
IMAGE_ICON       = 1
LR_LOADFROMFILE  = 0x00000010


# ─────────────────────────────────────────────────────────────────────────
# Mutable state (thread-safe [value] pattern)
# ─────────────────────────────────────────────────────────────────────────

_cached_hicon_big   = [None]
_cached_hicon_small = [None]
_root_hwnd          = [None]
_target_hwnd        = [0]


# ─────────────────────────────────────────────────────────────────────────
# HWND management
# ─────────────────────────────────────────────────────────────────────────

def get_root_hwnd():
    """Retourne le HWND du cadre Windows de root.
    Utilise wm_frame() en priorité — c'est le handle du cadre WM.
    """
    if not _root_hwnd[0]:
        try:
            frame = ui.root.wm_frame()
            if frame and frame not in ("0x0", "0"):
                _root_hwnd[0] = int(frame, 16)
        except Exception:
            pass
        if not _root_hwnd[0]:
            try:
                _root_hwnd[0] = _u32.GetParent(ui.root.winfo_id())
            except Exception:
                pass
    return _root_hwnd[0]


def invalidate_hwnd_cache():
    """Invalide le cache HWND (après overrideredirect change)."""
    _root_hwnd[0] = None


# ─────────────────────────────────────────────────────────────────────────
# Focus management (post-transcription paste)
# ─────────────────────────────────────────────────────────────────────────

def capture_target_window():
    """Mémorise la fenêtre active au moment du déclenchement du hotkey."""
    try:
        hwnd = _u32.GetForegroundWindow()
        root_hwnd = _root_hwnd[0]
        if hwnd and root_hwnd and hwnd != root_hwnd:
            _target_hwnd[0] = hwnd
    except Exception:
        pass


def restore_target_focus():
    """Remet le focus sur la fenêtre cible avant le collage.
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
            if attached:
                _u32.AttachThreadInput(our_tid, fg_tid, False)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────
# Icon management (GDI cache)
# ─────────────────────────────────────────────────────────────────────────

def apply_icon_to_hwnd(hwnd, ico_path):
    """Applique whisper_helio.ico via triple méthode (Tkinter + WM_SETICON)."""
    if not os.path.exists(ico_path):
        return
    try:
        ui.root.iconbitmap(ico_path)
    except Exception:
        pass
    if hwnd:
        try:
            if _cached_hicon_big[0] is None:
                _cached_hicon_big[0] = _u32.LoadImageW(
                    None, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            if _cached_hicon_small[0] is None:
                _cached_hicon_small[0] = _u32.LoadImageW(
                    None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
            if _cached_hicon_big[0]:
                _u32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, _cached_hicon_big[0])
            if _cached_hicon_small[0]:
                _u32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, _cached_hicon_small[0])
        except Exception as e:
            ui.log_error(e, "WM_SETICON taskbar")


def destroy_icons():
    """Détruit les HICON cachés (appelé au cleanup)."""
    for ref in (_cached_hicon_big, _cached_hicon_small):
        try:
            if ref[0]:
                _u32.DestroyIcon(ref[0])
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────
# Rounded corners (root window)
# ─────────────────────────────────────────────────────────────────────────

def apply_rounded(event=None, corner_radius=18):
    """Applique coins arrondis + WS_EX_TOOLWINDOW + WS_EX_NOACTIVATE sur root."""
    try:
        HWND = get_root_hwnd()
        if not HWND:
            return
        ex_style = _u32.GetWindowLongPtrW(HWND, GWL_EXSTYLE)
        _u32.SetWindowLongPtrW(
            HWND, GWL_EXSTYLE,
            (ex_style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        )
        w, h = ui.root.winfo_width(), ui.root.winfo_height()
        if w > 10 and h > 10:
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(
                0, 0, w + 1, h + 1, corner_radius * 2, corner_radius * 2)
            if hrgn:
                if not _u32.SetWindowRgn(HWND, hrgn, True):
                    ctypes.windll.gdi32.DeleteObject(hrgn)
    except Exception as e:
        ui.log_error(e, "apply_rounded")


# ─────────────────────────────────────────────────────────────────────────
# Resize/drag helpers (pure functions)
# ─────────────────────────────────────────────────────────────────────────

BORDER = 6

CURSOR_MAP = {
    "e": "size_we", "w": "size_we", "n": "size_ns", "s": "size_ns",
    "ne": "size_ne_sw", "sw": "size_ne_sw", "nw": "size_nw_se", "se": "size_nw_se",
}


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
