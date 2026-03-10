# -*- mode: python ; coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
#  Whisper Hélio v1.5 — PyInstaller .spec
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

# ── Fix décompression DLL (zlib level 9 → 0) ─────────────────────────────
# PyInstaller 6.19 compresse les DLL avec zlib max dans le CArchive/PKG.
# ctranslate2.dll (58 Mo) et d'autres se corrompent → "return code -3".
# Désactiver la compression : exe ~20% plus gros mais extraction fiable.
import PyInstaller.archive.writers
PyInstaller.archive.writers.CArchiveWriter._COMPRESSION_LEVEL = 0

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
    # Documentation (bouton Aide)
    ('README.md', '.'),
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

# Données tkinterdnd2 (DLLs Tcl/tkdnd pour le drag-and-drop natif)
try:
    datas += collect_data_files('tkinterdnd2')
except Exception:
    pass

# Données onnxruntime (Silero VAD pour BatchedInferencePipeline)
try:
    datas += collect_data_files('onnxruntime')
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

try:
    binaries += collect_dynamic_libs('onnxruntime')
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

    # Modules internes Whisper Hélio
    'core.streaming',
    'core.export',
    'core.macros',
    'core.hotkeys',
    'core.model',
    'core.transcription',

    # Audio (extension native PortAudio)
    'sounddevice',
    # Note : _sounddevice_data retiré — déjà couvert par collect_data_files

    # Saisie / automatisation
    'pyautogui',
    'pyperclip',
    'keyboard',   # F-keys via WH_KEYBOARD_LL (GetAsyncKeyState seul ne fonctionne pas partout)

    # Numpy (extension C, sous-module critique)
    'numpy',
    'numpy.core',
    'numpy.core._multiarray_umath',

    # PyAV — décodage audio pour transcription de fichiers (MP3, M4A, etc.)
    'av',

    # onnxruntime — Silero VAD pour BatchedInferencePipeline (4-5x plus rapide)
    'onnxruntime',
]

# Torch (optionnel — GPU uniquement, ~2 Go)
# Inclus seulement si installé dans l'environnement de build
try:
    import torch
    hiddenimports += ['torch', 'torch.cuda']
except ImportError:
    pass  # build CPU-only, exe beaucoup plus léger

# tkinterdnd2 (drag-and-drop fichiers audio)
try:
    import tkinterdnd2
    hiddenimports += ['tkinterdnd2']
except ImportError:
    pass  # drag-and-drop non disponible (le bouton 📂 reste fonctionnel)

# pycaw / comtypes (contrôle volume micro à 100%)
hiddenimports += ['pycaw', 'pycaw.pycaw', 'comtypes', 'comtypes.stream']

# Stdlib : retiré de hiddenimports — PyInstaller les détecte automatiquement
# (tkinter, ctypes, json, threading, etc. sont tous des imports top-level)

# ── Exclusions (allège le .exe) ───────────────────────────────────────────────
excludes = [
    # ── Gros packages inutiles (le code gère leur absence via try/except) ──
    'torch', 'torchvision', 'torchaudio', 'torch._C',
    'matplotlib',
    'PIL',
    'scipy',
    'pandas',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'transformers',
    # onnxruntime RÉINTÉGRÉ — nécessaire pour Silero VAD (BatchedInferencePipeline)
    'cv2', 'opencv',
    'numba',
    'pyarrow',
    'pygments',
    'cryptography',
    'pydantic',
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

# ── Mode ONEDIR : les DLL restent sur disque (pas d'extraction temp) ──────
# Résout définitivement "Failed to extract ... decompression return code -3"
# causé par Windows Defender qui bloque l'extraction des DLL dans %TEMP%.
exe = EXE(
    pyz,
    a.scripts,
    [],                           # PAS de binaries/datas ici (→ COLLECT)
    name='WhisperHelio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=['ctranslate2.dll', 'cudnn64_12.dll', 'cudnn_ops64_12.dll', 'cudnn_cnn64_12.dll'],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
    version_info=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=['ctranslate2.dll', 'cudnn64_12.dll', 'cudnn_ops64_12.dll', 'cudnn_cnn64_12.dll'],
    name='WhisperHelio',          # dossier dist/WhisperHelio/
)

# ── Post-build : copier l'icône dans le dossier de l'exe ─────────────────
import shutil as _shutil
_dist_icon = os.path.join(HERE, 'dist', 'WhisperHelio', 'whisper_helio.ico')
if os.path.exists(ICON) and not os.path.exists(_dist_icon):
    try:
        _shutil.copy2(ICON, _dist_icon)
        print(f"INFO: Icone copiee dans dist/WhisperHelio/ pour le raccourci bureau")
    except Exception as _e:
        print(f"WARNING: Impossible de copier l'icone : {_e}")
