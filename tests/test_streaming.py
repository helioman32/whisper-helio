"""
Tests pour core/streaming.py — StreamingTranscriber.

Note : les tests ne chargent pas de vrai modèle Whisper
(trop lourd pour les tests unitaires). On teste la logique.
"""
import numpy as np
import threading
import pytest

from core.streaming import StreamingTranscriber, _MIN_CHUNK_SAMPLES


# ── StreamingTranscriber — construction ──────────────────────────────────


class TestStreamingTranscriberInit:

    def test_default_state(self):
        st = StreamingTranscriber()
        assert st.is_ready is False
        assert st.enabled is True
        assert st.last_text == ""

    def test_custom_language(self):
        st = StreamingTranscriber(language="en")
        assert st._language == "en"

    def test_device_param_accepted(self):
        """Le paramètre device doit être accepté (compat) même s'il n'est plus stocké."""
        st = StreamingTranscriber(device="cuda")
        # Pas de crash = OK

    def test_on_log_callback(self):
        logs = []
        st = StreamingTranscriber(on_log=lambda msg: logs.append(msg))
        st._log("test message")
        assert len(logs) == 1
        assert logs[0] == "test message"


# ── enabled / disabled ───────────────────────────────────────────────────


class TestStreamingEnabled:

    def test_enable_disable(self):
        st = StreamingTranscriber()
        assert st.enabled is True
        st.enabled = False
        assert st.enabled is False

    def test_disabled_returns_cache(self):
        st = StreamingTranscriber()
        st._last_text = "cached"
        st.enabled = False
        audio = np.ones(10000, dtype=np.float32)
        result = st.transcribe_chunk(audio)
        assert result == "cached"


# ── transcribe_chunk — sans modèle ──────────────────────────────────────


class TestTranscribeChunkNoModel:

    def test_no_model_returns_cache(self):
        st = StreamingTranscriber()
        st._last_text = "previous"
        audio = np.ones(10000, dtype=np.float32)
        result = st.transcribe_chunk(audio)
        assert result == "previous"

    def test_too_short_returns_cache(self):
        st = StreamingTranscriber()
        st._last_text = "cached"
        short = np.ones(_MIN_CHUNK_SAMPLES - 1, dtype=np.float32)
        result = st.transcribe_chunk(short)
        assert result == "cached"

    def test_empty_audio_returns_cache(self):
        st = StreamingTranscriber()
        st._last_text = "cached"
        result = st.transcribe_chunk(np.array([], dtype=np.float32))
        assert result == "cached"


# ── dtype conversion ─────────────────────────────────────────────────────


class TestDtypeConversion:

    def test_float64_accepted(self):
        """float64 ne doit pas crasher (conversion interne)."""
        st = StreamingTranscriber()
        audio = np.ones(10000, dtype=np.float64)
        # Pas de modèle → retourne cache, mais pas de crash
        result = st.transcribe_chunk(audio)
        assert isinstance(result, str)


# ── reset / unload ───────────────────────────────────────────────────────


class TestResetUnload:

    def test_reset_clears_text(self):
        st = StreamingTranscriber()
        st._last_text = "something"
        st.reset()
        assert st.last_text == ""

    def test_unload_clears_all(self):
        st = StreamingTranscriber()
        st._last_text = "something"
        st._loading = True
        st.unload()
        assert st._model is None
        assert st._last_text == ""
        assert st._loading is False


# ── set_language ─────────────────────────────────────────────────────────


class TestSetLanguage:

    def test_set_language(self):
        st = StreamingTranscriber(language="fr")
        st.set_language("de")
        assert st._language == "de"


# ── Thread safety ────────────────────────────────────────────────────────


class TestThreadSafety:

    def test_concurrent_transcribe_no_crash(self):
        """Appels concurrents à transcribe_chunk ne doivent pas crasher."""
        st = StreamingTranscriber()
        errors = []

        def worker():
            try:
                for _ in range(50):
                    audio = np.random.randn(10000).astype(np.float32)
                    st.transcribe_chunk(audio)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0

    def test_load_async_double_call(self):
        """Deux appels à load_async ne doivent pas lancer deux threads."""
        st = StreamingTranscriber()
        st._loading = True  # simuler un chargement en cours
        st.load_async()  # ne doit rien faire
        # Pas de crash = OK
