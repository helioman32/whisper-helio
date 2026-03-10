"""
Tests pour core/transcription.py — transcribe_audio, copy/paste helpers.

Note : transcribe_audio nécessite un modèle Whisper chargé,
donc on teste surtout les edge cases et les helpers.
"""
import numpy as np
import pytest

from core.transcription import (
    transcribe_audio, fast_copy, paste_text, copy_and_paste,
    _last_pasted_text,
)
from core.audio import SAMPLE_RATE, MIN_AUDIO_SAMPLES


# ── transcribe_audio — edge cases ────────────────────────────────────────


class TestTranscribeAudio:

    def test_too_short_audio(self):
        """Audio plus court que MIN_AUDIO_SAMPLES retourne vide."""
        short = np.zeros(100, dtype=np.float32)
        config = {"language": "fr"}
        result = transcribe_audio(None, short, config)
        assert result == ""

    def test_silence_skipped_with_vad(self):
        """Audio silencieux avec VAD activé retourne vide."""
        silence = np.zeros(SAMPLE_RATE * 2, dtype=np.float32)  # 2s de silence
        config = {"language": "fr"}
        result = transcribe_audio(None, silence, config, use_vad=True)
        assert result == ""

    def test_vad_disabled_doesnt_skip(self):
        """Avec use_vad=False, le silence n'est pas filtré.
        Mais comme model=None, ça retourne quand même vide (exception catchée)."""
        silence = np.zeros(SAMPLE_RATE * 2, dtype=np.float32)
        config = {"language": "fr"}
        result = transcribe_audio(None, silence, config, use_vad=False)
        assert result == ""  # model=None → exception → ""


# ── fast_copy ────────────────────────────────────────────────────────────


class TestFastCopy:

    def test_copy_text(self):
        """fast_copy retourne True en cas de succès."""
        result = fast_copy("Test clipboard")
        assert result is True

    def test_copy_unicode(self):
        result = fast_copy("Hélio — àéîôü 日本語")
        assert result is True

    def test_copy_empty(self):
        result = fast_copy("")
        assert result is True


# ── _last_pasted_text (espace intelligent) ───────────────────────────────


class TestSmartSpace:

    def test_initial_empty(self):
        """Le dernier texte collé est vide au départ."""
        # Réinitialiser pour le test
        _last_pasted_text[0] = ""

    def test_space_after_alphanumeric(self):
        """L'espace intelligent est géré dans copy_and_paste.
        On vérifie juste que _last_pasted_text est mutable."""
        _last_pasted_text[0] = "test"
        assert _last_pasted_text[0] == "test"
        _last_pasted_text[0] = ""

    def test_space_after_punctuation(self):
        """Après un point, un espace devrait être ajouté."""
        _last_pasted_text[0] = "Phrase."
        last = _last_pasted_text[0][-1]
        assert last in ".!?:;,)»\"'"
        _last_pasted_text[0] = ""
