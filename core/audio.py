"""
Whisper Hélio — Audio : RingBuffer, VAD, constantes

Ce module contient les composants audio réutilisables et testables :
- RingBuffer thread-safe pour l'enregistrement circulaire
- has_voice() : détection d'activité vocale (VAD) par RMS
- Constantes audio (sample rate, durées, seuils)

Aucune dépendance vers tkinter, sounddevice, ou l'UI.
"""

import math
import threading

import numpy as np


# ── Constantes audio ──────────────────────────────────────────────────────
SAMPLE_RATE = 16000
MAX_RECORD_SECONDS = 120
MIN_AUDIO_SAMPLES = 8000
AUDIO_BLOCKSIZE = 4096
VAD_THRESHOLD = 0.003


# ── Constantes mode réunion ───────────────────────────────────────────────
MEETING_SILENCE_THRESHOLD = 1.2
MEETING_MAX_DURATION      = 30.0
MEETING_POLL              = 0.05
MEETING_MIN_VOICE_DURATION = 0.8
MEETING_GRACE_PERIOD      = 2.0
MEETING_GRACE_SILENCE     = 0.3


# ── RingBuffer ────────────────────────────────────────────────────────────

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
        data_flat = data.ravel()
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
            if self.write_pos == 0:
                return self.buffer.copy()
            return np.concatenate([
                self.buffer[self.write_pos:],
                self.buffer[:self.write_pos]
            ])

    def get_tail(self, n):
        """Récupère les n derniers échantillons sans copier tout le buffer."""
        with self.lock:
            if self.length == 0 or n <= 0:
                return np.array([], dtype=np.float32)
            n = min(n, self.length)
            if self.length < self.max_samples:
                return self.buffer[self.length - n:self.length].copy()
            start = (self.write_pos - n) % self.max_samples
            if start + n <= self.max_samples:
                return self.buffer[start:start + n].copy()
            return np.concatenate([
                self.buffer[start:],
                self.buffer[:n - (self.max_samples - start)]
            ])

    def clear(self):
        """Vide le buffer."""
        with self.lock:
            self.write_pos = 0
            self.length = 0


# ── VAD (Voice Activity Detection) ───────────────────────────────────────

def has_voice(audio_data, threshold=VAD_THRESHOLD):
    """Détecte si l'audio contient de la voix (RMS via np.dot — zéro allocation)."""
    if len(audio_data) == 0:
        return False
    data = audio_data if audio_data.dtype == np.float32 else audio_data.astype(np.float32)
    flat = data.ravel()
    rms = (np.dot(flat, flat) / flat.size) ** 0.5
    return math.isfinite(rms) and rms > threshold
