"""
core/hotkeys.py — Détection des raccourcis clavier (hotkeys).
Hybride GetAsyncKeyState (WinAPI) + keyboard lib (fallback).
Zéro dépendance Tkinter, zéro hook souris.
"""
from __future__ import annotations

import ctypes
import time

# ── WinAPI (user32.dll) ────────────────────────────────────────────────────
_u32 = ctypes.windll.user32

_GetAsyncKeyState = _u32.GetAsyncKeyState
_GetAsyncKeyState.argtypes = [ctypes.c_int]
_GetAsyncKeyState.restype  = ctypes.c_short

_keybd_event = _u32.keybd_event
_keybd_event.argtypes = [ctypes.c_byte, ctypes.c_byte, ctypes.c_ulong, ctypes.c_void_p]
_keybd_event.restype  = None

_KEYEVENTF_KEYUP = 0x0002
_VK_CONTROL = 0x11
_VK_V       = 0x56

# ── Virtual Key codes ──────────────────────────────────────────────────────
VK_CODES = {
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "pause": 0x13, "scroll_lock": 0x91, "insert": 0x2D,
    "mouse_x1": 0x05, "mouse_x2": 0x06,  # VK_XBUTTON1 / VK_XBUTTON2
}

# ── keyboard lib (optionnel) ──────────────────────────────────────────────
try:
    import keyboard as _kb
    _has_keyboard = True
except ImportError:
    _has_keyboard = False


# ── Détection hotkey ──────────────────────────────────────────────────────

def is_hotkey_pressed(hk: str) -> bool:
    """Vérifie si le hotkey est pressé.
    GetAsyncKeyState EN PRIORITÉ — API directe, pas de hook, fiable après reboot.
    keyboard lib en fallback seulement (son hook WH_KEYBOARD_LL peut être
    silencieusement supprimé par Windows si le système est chargé au boot).
    """
    # 1) GetAsyncKeyState — toujours fiable (pas de hook, requête directe au noyau)
    vk = VK_CODES.get(hk)
    if vk is not None and bool(_GetAsyncKeyState(vk) & 0x8000):
        return True
    # 2) Fallback keyboard lib pour les cas où GetAsyncKeyState rate la touche
    if _has_keyboard and not hk.startswith("mouse_"):
        try:
            return _kb.is_pressed(hk)
        except Exception:
            pass
    return False


def send_ctrl_v() -> None:
    """Envoie Ctrl+V via keybd_event (pas de hook système)."""
    _keybd_event(_VK_CONTROL, 0, 0, 0)
    _keybd_event(_VK_V, 0, 0, 0)
    time.sleep(0.02)
    _keybd_event(_VK_V, 0, _KEYEVENTF_KEYUP, 0)
    _keybd_event(_VK_CONTROL, 0, _KEYEVENTF_KEYUP, 0)
