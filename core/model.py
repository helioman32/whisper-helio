"""
core/model.py — Chargement du modèle Whisper avec fallback GPU → CPU.
Retourne (model, device, compute) — zéro global, zéro dépendance Tkinter.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np

from core.audio import SAMPLE_RATE
from core.config import log_error

# ── Constantes WhisperModel ───────────────────────────────────────────────
_NUM_WORKERS = 4   # 4 streams parallèles → pipeline GPU/CPU
_CPU_THREADS = 4   # sweet spot prouvé (8 → thread contention)


# ── Détection cache HuggingFace ───────────────────────────────────────────

def is_model_cached(model_name: str) -> Tuple[bool, str, int]:
    """Vérifie si le modèle Whisper est déjà téléchargé en cache HuggingFace.

    Returns
    -------
    (cached, repo_dir, total_bytes)
    """
    try:
        try:
            from faster_whisper.utils import _MODELS
        except ImportError:
            _MODELS = {}
        repo_id = _MODELS.get(model_name, model_name)
        cache_dir = os.path.join(str(Path.home()), ".cache", "huggingface", "hub")
        repo_dir = os.path.join(cache_dir, "models--" + repo_id.replace("/", "--"))
        if not os.path.isdir(repo_dir):
            return False, repo_dir, 0
        # Parcours unique : taille + détection model.bin
        total = 0
        has_model_bin = False
        for dp, _, fnames in os.walk(repo_dir):
            for f in fnames:
                total += os.path.getsize(os.path.join(dp, f))
                if not has_model_bin and f.endswith("model.bin"):
                    has_model_bin = True
        return has_model_bin, repo_dir, total
    except Exception:
        return True, "", 0   # en cas d'erreur, on suppose qu'il est en cache


# Tailles approximatives des modèles (model.bin + config) en octets
MODEL_SIZES = {
    "tiny": 77_000_000, "base": 148_000_000, "small": 490_000_000,
    "medium": 1_530_000_000, "large-v2": 3_090_000_000,
    "large-v3": 3_090_000_000, "large-v3-turbo": 1_620_000_000,
}


# ── Chargement avec fallback ─────────────────────────────────────────────

def load_model(
    config: dict,
    device: str,
    compute: str,
    on_status: Optional[Callable[[str], None]] = None,
) -> Tuple[object, str, str]:
    """Charge le modèle Whisper avec fallback GPU float16 → CPU int8 et warmup.

    Parameters
    ----------
    config : dict de configuration (clés : "model", "language")
    device : "cuda" ou "cpu"
    compute : "float16", "int8", etc.
    on_status : callback(text) pour afficher la progression

    Returns
    -------
    (model, device, compute) — model est None si tout a échoué
    """
    model_name = config["model"]

    def _status(txt):
        if on_status:
            on_status(txt)

    # ── Progression du téléchargement si le modèle n'est pas en cache ────
    cached, repo_dir, _ = is_model_cached(model_name)
    _dl_stop = threading.Event()
    if not cached:
        expected = MODEL_SIZES.get(model_name, 3_000_000_000)
        expected_mb = expected / (1024 * 1024)

        def _monitor_download():
            """Thread qui surveille la taille du dossier cache."""
            while not _dl_stop.is_set():
                try:
                    if os.path.isdir(repo_dir):
                        current = sum(
                            os.path.getsize(os.path.join(dp, f))
                            for dp, _, fnames in os.walk(repo_dir) for f in fnames
                        )
                        current_mb = current / (1024 * 1024)
                        pct = min(99, int(current / expected * 100))
                        _status(f"Telechargement {model_name} : "
                                f"{current_mb:.0f}/{expected_mb:.0f} Mo ({pct}%)")
                except Exception:
                    pass
                _dl_stop.wait(0.5)

        _status(f"Telechargement {model_name}...")
        threading.Thread(target=_monitor_download, daemon=True).start()

    # Import lazy de faster_whisper (économise ~1.5s au démarrage)
    from faster_whisper import WhisperModel

    model = None
    try:
        _dev_label = "GPU" if device == "cuda" else "CPU"
        _status(f"Chargement {model_name} ({_dev_label} {compute})...")
        model = WhisperModel(model_name, device=device, compute_type=compute,
                             num_workers=_NUM_WORKERS, cpu_threads=_CPU_THREADS)
    except Exception as e:
        log_error(e, f"Impossible de charger le modèle {model_name} "
                      f"sur {device}/{compute}")
        # Fallback CUDA → CPU int8
        if device == "cuda":
            try:
                log_error(msg="Fallback CUDA → CPU")
                device, compute = "cpu", "int8"
                model = WhisperModel(model_name, device="cpu", compute_type="int8",
                                     num_workers=_NUM_WORKERS, cpu_threads=_CPU_THREADS)
            except Exception as e2:
                log_error(e2, "Fallback CPU aussi échoué")
        if model is None:
            for fallback in ["base", "tiny"]:
                try:
                    _status(f"Fallback {fallback}...")
                    device, compute = "cpu", "int8"
                    model = WhisperModel(fallback, device="cpu", compute_type="int8",
                                         num_workers=_NUM_WORKERS, cpu_threads=_CPU_THREADS)
                    break
                except Exception:
                    continue
    finally:
        _dl_stop.set()   # toujours arrêter le thread de monitoring téléchargement
    if model is None:
        return None, device, compute

    # Warmup — bruit blanc 0.5s, compile les kernels CUDA
    _dev_label = "GPU" if device == "cuda" else "CPU"
    _status(f"Initialisation {_dev_label}...")
    warmup_ok = False
    rng = np.random.RandomState(42)
    dummy = (rng.randn(SAMPLE_RATE // 2) * 0.02).astype(np.float32)
    try:
        list(model.transcribe(dummy, language=config["language"],
                              without_timestamps=True)[0])
        log_error(msg=f"[WARMUP] OK ({_dev_label})")
        warmup_ok = True
    except Exception as e:
        log_error(e, f"Warmup {device}/{compute} échoué")
        if device == "cuda":
            log_error(msg="Warmup CUDA échoué — fallback CPU")
            device, compute = "cpu", "int8"
            _status("Initialisation CPU...")
            try:
                model = WhisperModel(model_name, device="cpu", compute_type="int8",
                                     num_workers=_NUM_WORKERS, cpu_threads=_CPU_THREADS)
                list(model.transcribe(dummy, language=config["language"],
                                      without_timestamps=True)[0])
                warmup_ok = True
            except Exception as e2:
                log_error(e2, "Warmup CPU aussi échoué")
                model = None
    if not warmup_ok:
        return None, device, compute
    return model, device, compute
