"""
Tests pour core/audio.py — RingBuffer, VAD, constantes.
"""
import numpy as np
import threading
import pytest

from core.audio import (
    RingBuffer, has_voice,
    SAMPLE_RATE, MIN_AUDIO_SAMPLES, VAD_THRESHOLD,
)


# ── RingBuffer ───────────────────────────────────────────────────────────


class TestRingBuffer:

    def test_empty(self):
        buf = RingBuffer(1000)
        data = buf.get_data()
        assert len(data) == 0
        assert data.dtype == np.float32

    def test_append_and_get(self):
        buf = RingBuffer(1000)
        samples = np.ones(500, dtype=np.float32)
        buf.append(samples)
        data = buf.get_data()
        assert len(data) == 500
        assert np.all(data == 1.0)

    def test_wrap_around(self):
        """Quand le buffer est plein, les anciennes données sont écrasées."""
        buf = RingBuffer(100)
        buf.append(np.ones(80, dtype=np.float32) * 1.0)
        buf.append(np.ones(50, dtype=np.float32) * 2.0)
        data = buf.get_data()
        assert len(data) == 100
        # Les 50 derniers échantillons doivent être 2.0
        assert np.all(data[-50:] == 2.0)

    def test_overflow_single_append(self):
        """Un append plus grand que le buffer ne crash pas."""
        buf = RingBuffer(100)
        big = np.arange(200, dtype=np.float32)
        buf.append(big)
        data = buf.get_data()
        assert len(data) == 100
        # Doit contenir les 100 derniers échantillons
        np.testing.assert_array_equal(data, big[-100:])

    def test_clear(self):
        buf = RingBuffer(1000)
        buf.append(np.ones(500, dtype=np.float32))
        buf.clear()
        assert len(buf.get_data()) == 0

    def test_get_tail(self):
        buf = RingBuffer(1000)
        samples = np.arange(500, dtype=np.float32)
        buf.append(samples)
        tail = buf.get_tail(10)
        assert len(tail) == 10
        np.testing.assert_array_equal(tail, np.arange(490, 500, dtype=np.float32))

    def test_get_tail_more_than_length(self):
        buf = RingBuffer(1000)
        buf.append(np.ones(50, dtype=np.float32))
        tail = buf.get_tail(100)
        assert len(tail) == 50  # clampé à la taille du buffer

    def test_get_tail_empty(self):
        buf = RingBuffer(1000)
        assert len(buf.get_tail(10)) == 0

    def test_get_tail_zero(self):
        buf = RingBuffer(1000)
        buf.append(np.ones(50, dtype=np.float32))
        assert len(buf.get_tail(0)) == 0

    def test_get_tail_after_wrap(self):
        """get_tail après un wrap-around."""
        buf = RingBuffer(100)
        buf.append(np.ones(80, dtype=np.float32) * 1.0)
        buf.append(np.ones(50, dtype=np.float32) * 2.0)
        tail = buf.get_tail(30)
        assert len(tail) == 30
        assert np.all(tail == 2.0)  # les 30 derniers sont tous 2.0

    def test_thread_safety(self):
        """Accès concurrent sans crash."""
        buf = RingBuffer(10000)
        errors = []

        def writer():
            try:
                for _ in range(100):
                    buf.append(np.random.randn(100).astype(np.float32))
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    buf.get_data()
                    buf.get_tail(50)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=writer))
            threads.append(threading.Thread(target=reader))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0

    def test_2d_input(self):
        """Append avec un array 2D (comme sounddevice callback)."""
        buf = RingBuffer(1000)
        # sounddevice retourne (blocksize, channels) → (1024, 1)
        data_2d = np.ones((256, 1), dtype=np.float32)
        buf.append(data_2d)
        result = buf.get_data()
        assert len(result) == 256


# ── has_voice ────────────────────────────────────────────────────────────


class TestHasVoice:

    def test_silence(self):
        silence = np.zeros(1000, dtype=np.float32)
        assert not has_voice(silence)

    def test_loud_signal(self):
        loud = np.ones(1000, dtype=np.float32) * 0.5
        assert has_voice(loud)

    def test_quiet_noise(self):
        quiet = np.ones(1000, dtype=np.float32) * 0.001
        assert not has_voice(quiet)  # sous le seuil 0.003

    def test_empty_array(self):
        assert not has_voice(np.array([], dtype=np.float32))

    def test_custom_threshold(self):
        signal = np.ones(1000, dtype=np.float32) * 0.01
        assert has_voice(signal, threshold=0.005)
        assert not has_voice(signal, threshold=0.05)

    def test_nan_handling(self):
        """NaN dans l'audio ne doit pas retourner True."""
        nan_data = np.full(1000, np.nan, dtype=np.float32)
        assert not has_voice(nan_data)

    def test_int16_input(self):
        """has_voice doit aussi fonctionner avec int16 (conversion interne)."""
        data = np.ones(1000, dtype=np.int16) * 1000
        # Devrait fonctionner grâce à la conversion interne
        result = has_voice(data)
        assert bool(result) is True  # np.bool_ → bool


# ── Constantes ───────────────────────────────────────────────────────────


class TestConstants:

    def test_sample_rate(self):
        assert SAMPLE_RATE == 16000

    def test_min_audio_samples(self):
        assert MIN_AUDIO_SAMPLES == 8000  # 0.5s à 16kHz

    def test_vad_threshold(self):
        assert 0 < VAD_THRESHOLD < 1
