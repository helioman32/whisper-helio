# -*- mode: python ; coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
#  Whisper Hélio v1.4 — PyInstaller .spec
#  Génère : dist/WhisperHelio.exe  (fichier unique, sans console)
#
#  Usage :
#      pyinstaller whisper_helio.spec
#
#  Prérequis :
#      pip install pyinstaller
#      (tous les packages de l'app déjà installés dans l'environnement)
# ══════════════════════════════════════════════════════════════════════════════

import sys
import os
import shutil
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# ── Vérification UPX ────────────────────────────────────────────────────────
if not shutil.which('upx'):
    print("WARNING: UPX non trouve dans le PATH. Le binaire ne sera pas compresse.")
    print("  Installez UPX : https://github.com/upx/upx/releases")

# ── Chemins ───────────────────────────────────────────────────────────────────
HERE   = os.path.dirname(os.path.abspath(SPEC))   # dossier du .spec
SCRIPT = os.path.join(HERE, 'dictee.pyw')
ICON   = os.path.join(HERE, 'whisper_helio.ico')

# ── Données à embarquer ───────────────────────────────────────────────────────
datas = [
    # Icône de l'application
    (ICON, '.'),
]

# Données faster-whisper (modèles de tokenisation, assets)
try:
    datas += collect_data_files('faster_whisper')
except Exception:
    pass

# Données ctranslate2 (kernels CUDA / CPU)
try:
    datas += collect_data_files('ctranslate2')
except Exception:
    pass

# Données sounddevice / PortAudio
try:
    datas += collect_data_files('sounddevice')
except Exception:
    pass

# ── Bibliothèques dynamiques ──────────────────────────────────────────────────
binaries = []

try:
    binaries += collect_dynamic_libs('ctranslate2')
except Exception:
    pass

try:
    binaries += collect_dynamic_libs('sounddevice')
except Exception:
    pass

# ── Imports cachés (détection automatique insuffisante) ───────────────────────
hiddenimports = [
    # faster-whisper / ctranslate2 (extensions natives, détection auto insuffisante)
    'faster_whisper',
    'faster_whisper.transcribe',
    'faster_whisper.audio',
    'faster_whisper.feature_extractor',
    'faster_whisper.tokenizer',
    'ctranslate2',
    # Note : ctranslate2.converters retiré — inutile au runtime (conversion modèles)

    # Audio (extension native PortAudio)
    'sounddevice',
    # Note : _sounddevice_data retiré — déjà couvert par collect_data_files

    # Saisie / automatisation
    'keyboard',
    'pyautogui',
    'pyperclip',
    # Note : pynput retiré — le code utilise keyboard, pas pynput

    # Numpy (extension C, sous-module critique)
    'numpy',
    'numpy.core',
    'numpy.core._multiarray_umath',
]

# Torch (optionnel — GPU uniquement, ~2 Go)
# Inclus seulement si installé dans l'environnement de build
try:
    import torch
    hiddenimports += ['torch', 'torch.cuda']
except ImportError:
    pass  # build CPU-only, exe beaucoup plus léger

# Stdlib : retiré de hiddenimports — PyInstaller les détecte automatiquement
# (tkinter, ctypes, json, threading, etc. sont tous des imports top-level)

# ── Exclusions (allège le .exe) ───────────────────────────────────────────────
excludes = [
    'matplotlib',
    'PIL',
    'scipy',
    'pandas',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    # NE PAS exclure setuptools/distutils : les hooks PyInstaller en ont besoin
    # NE PAS exclure email, html, http, urllib, xml :
    # huggingface_hub en a besoin pour télécharger le modèle au 1er lancement
    'xmlrpc',
    'unittest',
    'doctest',
    'pydoc',
    'lib2to3',
    'curses',
    'readline',
]

# ══════════════════════════════════════════════════════════════════════════════
#  Pipeline PyInstaller
# ══════════════════════════════════════════════════════════════════════════════

a = Analysis(
    [SCRIPT],
    pathex=[HERE],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,          # supprime les assert et docstrings → léger gain
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WhisperHelio',          # nom du .exe final
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,                  # strip ne fonctionne pas sur Windows PE — laisser False
    upx=True,                     # compresse les binaires (UPX requis, voir check ci-dessus)
    upx_exclude=[
        'vcruntime140.dll',
        'python3*.dll',
        '_ctypes*.pyd',
    ],
    runtime_tmpdir=None,
    console=False,                # pas de fenêtre console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
    version_info=None,
)
