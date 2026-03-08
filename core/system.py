"""
Whisper Hélio — Utilitaires système Windows

Ce module contient les fonctions utilitaires système :
- Adaptation résolution écran (_screen_scale, _fit_window)
- Création automatique du raccourci bureau

Dépendances : core.config (log_error), ctypes, os, sys, subprocess, pathlib.
"""

import ctypes
import os
import subprocess
import sys
from pathlib import Path

from core.config import log_error, MIN_W, MIN_H


# ── Adaptation résolution ────────────────────────────────────────────────
_REF_W, _REF_H = 1920, 1080


def dpi_scale():
    """Retourne le facteur DPI Windows (1.0 = 100%, 1.25 = 125%, 1.5 = 150%, 2.0 = 200%).

    Sans SetProcessDpiAwareness, GetDpiForSystem() et GetDeviceCaps mentent (96).
    Le registre Windows contient le vrai DPI appliqué par l'utilisateur.
    """
    # 1) Registre — seule source fiable sans DPI awareness
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Control Panel\Desktop\WindowMetrics") as key:
            dpi = winreg.QueryValueEx(key, "AppliedDPI")[0]
            if dpi > 0:
                return max(1.0, dpi / 96.0)
    except Exception:
        pass
    # 2) Fallback GetDpiForSystem (fonctionne si le process est DPI-aware)
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        if dpi > 96:
            return dpi / 96.0
    except Exception:
        pass
    return 1.0


def screen_scale():
    """Retourne un facteur d'échelle (0.0–1.0) basé sur la résolution.

    Sans SetProcessDpiAwareness, GetSystemMetrics retourne la résolution
    logique (virtuelle) — c'est ce que Tkinter utilise aussi.
    Sur un écran 1920x1080 → scale=1.0
    Sur un écran 1366x768 → scale=0.67
    """
    try:
        sw = ctypes.windll.user32.GetSystemMetrics(0)  # SM_CXSCREEN
        sh = ctypes.windll.user32.GetSystemMetrics(1)  # SM_CYSCREEN
    except Exception:
        return 1.0
    if sw <= 0 or sh <= 0:
        return 1.0
    scale_w = sw / _REF_W
    scale_h = sh / _REF_H
    return min(scale_w, scale_h, 1.0)  # jamais > 1.0


def fit_window(win_w, win_h, sw, sh, margin=40):
    """Ajuste win_w/win_h pour tenir dans l'écran avec une marge."""
    max_w = max(MIN_W, sw - margin)
    max_h = max(MIN_H, sh - margin)
    if win_w > max_w:
        win_w = max_w
    if win_h > max_h:
        win_h = max_h
    return max(MIN_W, int(win_w)), max(MIN_H, int(win_h))


# ── Raccourci bureau automatique ─────────────────────────────────────────

def create_desktop_shortcut():
    """Crée un raccourci .lnk sur le bureau au premier lancement."""
    try:
        desktop = Path(os.path.join(Path.home(), "Desktop"))
        if not desktop.exists():
            # Fallback : dossier Bureau français
            desktop = Path(os.path.join(Path.home(), "Bureau"))
        if not desktop.exists():
            return
        shortcut_path = desktop / "Whisper Hélio.lnk"
        if shortcut_path.exists():
            return  # raccourci déjà présent

        # Déterminer le chemin de l'exe (compilé) ou du script (dev)
        if getattr(sys, 'frozen', False):
            target = sys.executable
        else:
            # Mode développeur : pas de raccourci
            return

        # Chercher l'icône : à côté de l'exe, puis dans le bundle, puis exe,0
        app_dir = os.path.dirname(target)
        icon_loc = None
        # 1. Icône .ico à côté de l'exe
        ico_local = os.path.join(app_dir, "whisper_helio.ico")
        if os.path.exists(ico_local):
            icon_loc = ico_local
        # 2. Icône dans le bundle PyInstaller (_MEIPASS)
        if not icon_loc:
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                ico_bundled = os.path.join(meipass, "whisper_helio.ico")
                if os.path.exists(ico_bundled):
                    try:
                        import shutil
                        shutil.copy2(ico_bundled, ico_local)
                        icon_loc = ico_local
                    except Exception:
                        pass
        # 3. Fallback : icône embarquée dans l'exe
        if not icon_loc:
            icon_loc = f"{target},0"

        # Créer le raccourci via PowerShell
        def _ps_esc(s): return str(s).replace("'", "''")
        ps_script = (
            f"$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{_ps_esc(shortcut_path)}'); "
            f"$s.TargetPath = '{_ps_esc(target)}'; "
            f"$s.WorkingDirectory = '{_ps_esc(app_dir)}'; "
            f"$s.IconLocation = '{_ps_esc(icon_loc)}'; "
            f"$s.Description = 'Whisper Helio - Dictee vocale offline'; "
            f"$s.Save()"
        )
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
    except Exception as e:
        log_error(e, "desktop shortcut creation")
