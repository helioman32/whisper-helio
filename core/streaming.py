# -*- coding: utf-8 -*-
"""
Whisper Hélio — Module de transcription streaming temps réel.

Charge un modèle Whisper léger (tiny) en arrière-plan et fournit
un aperçu textuel en quasi-temps-réel pendant l'enregistrement.
La transcription finale reste assurée par le modèle principal (large-v3).

Architecture :
- StreamingTranscriber : classe autonome, aucune dépendance vers dictee.pyw
- Charge un modèle 'tiny' (~75 Mo RAM) séparément du modèle principal
- Transcrit périodiquement les dernières secondes du RingBuffer
- Thread-safe : un seul appel transcribe_chunk() à la fois (verrou interne)

Usage dans dictee.pyw :
    from core.streaming import StreamingTranscriber
    streamer = StreamingTranscriber(language="fr", device="cpu")
    # Pendant l'enregistrement, appel périodique :
    text = streamer.transcribe_chunk(audio_buffer.get_data())
    # Afficher text dans un label flottant
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

__all__ = ["StreamingTranscriber"]


# ── Constantes ────────────────────────────────────────────────────────────
_STREAMING_MODEL = "tiny"          # Modèle ultra-rapide pour l'aperçu
_STREAMING_COMPUTE_CPU = "int8"    # Compute type CPU (int8 = plus rapide)
_MIN_CHUNK_SAMPLES = 4800          # ~0.3s à 16kHz — en dessous, pas de transcription
_SAMPLE_RATE = 16000


class StreamingTranscriber:
    """Transcripteur streaming léger pour aperçu temps réel.

    Charge un modèle Whisper 'tiny' séparément du modèle principal.
    Thread-safe — un seul appel transcribe_chunk() simultané autorisé.

    Parameters
    ----------
    language : str
        Code langue ISO (ex: "fr", "en", "de").
    device : str
        "cuda" ou "cpu". Le modèle tiny tourne très bien sur CPU.
    on_log : callable, optional
        Fonction de log (signature: on_log(msg: str)).
    """

    def __init__(
        self,
        language: str = "fr",
        device: str = "cpu",
        on_log=None,
    ):
        self._language = language
        self._log = on_log or (lambda msg: None)
        self._model = None           # WhisperModel (chargé en arrière-plan)
        self._lock = threading.Lock() # un seul transcribe_chunk() à la fois
        self._loading = False
        self._ready = threading.Event()
        self._last_text = ""          # dernier texte transcrit (cache)
        self._enabled = True          # peut être désactivé via config

    # ── Propriétés ────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        """True si le modèle tiny est chargé et prêt."""
        return self._model is not None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def last_text(self) -> str:
        """Dernier texte transcrit (lecture thread-safe)."""
        return self._last_text

    # ── Chargement modèle (arrière-plan) ──────────────────────────────

    def load_async(self):
        """Charge le modèle tiny en arrière-plan (non bloquant).

        Appeler une seule fois au démarrage. Le modèle sera prêt
        quand is_ready == True (généralement 1-2 secondes).
        """
        if self._loading or self._model is not None:
            return
        self._loading = True
        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        """Charge le modèle tiny (thread interne)."""
        try:
            from faster_whisper import WhisperModel

            t0 = time.perf_counter()
            self._model = WhisperModel(
                _STREAMING_MODEL,
                device="cpu",       # tiny sur CPU toujours — ne pas concurrencer le GPU principal
                compute_type=_STREAMING_COMPUTE_CPU,
                cpu_threads=2,      # léger — ne pas voler les threads au modèle principal
                num_workers=1,
            )
            elapsed = time.perf_counter() - t0
            self._log(f"[STREAMING] Modèle {_STREAMING_MODEL} chargé en {elapsed:.1f}s (CPU {_STREAMING_COMPUTE_CPU})")
            self._ready.set()
        except Exception as e:
            self._log(f"[STREAMING] Échec chargement modèle {_STREAMING_MODEL}: {e}")
            self._model = None
        finally:
            self._loading = False

    # ── Transcription d'un chunk ──────────────────────────────────────

    def transcribe_chunk(self, audio_data: np.ndarray) -> str:
        """Transcrit un morceau d'audio et retourne le texte.

        Conçu pour être appelé périodiquement (~toutes les 1.5s)
        pendant l'enregistrement. Non bloquant si un appel est déjà
        en cours (retourne le dernier texte en cache).

        Parameters
        ----------
        audio_data : np.ndarray
            Audio float32, 16kHz, mono. Typiquement les dernières
            secondes du RingBuffer.

        Returns
        -------
        str
            Texte transcrit, ou chaîne vide si pas assez d'audio.
        """
        if not self._enabled or self._model is None:
            return self._last_text

        if len(audio_data) < _MIN_CHUNK_SAMPLES:
            return self._last_text

        # Garantir float32 (certains backends sounddevice peuvent retourner float64)
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        # Non bloquant : si un transcribe est déjà en cours, retourner le cache
        if not self._lock.acquire(blocking=False):
            return self._last_text

        try:
            segments, _ = self._model.transcribe(
                audio_data,
                language=self._language,
                beam_size=1,
                best_of=1,
                temperature=0,                    # greedy — maximum vitesse
                condition_on_previous_text=False,
                without_timestamps=True,
                no_speech_threshold=0.6,
                vad_filter=False,
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            self._last_text = text
            return text
        except Exception as e:
            self._log(f"[STREAMING] Erreur transcription chunk: {e}")
            return self._last_text
        finally:
            self._lock.release()

    # ── Mise à jour config ────────────────────────────────────────────

    def set_language(self, language: str):
        """Met à jour la langue pour les prochains chunks."""
        self._language = language

    # ── Nettoyage ─────────────────────────────────────────────────────

    def reset(self):
        """Réinitialise le cache texte (début d'un nouvel enregistrement)."""
        self._last_text = ""

    def unload(self):
        """Libère le modèle et la mémoire."""
        with self._lock:
            self._model = None
            self._last_text = ""
            self._ready.clear()
            self._loading = False
