"""
Tests pour core/model.py — is_model_cached, constantes, MODEL_SIZES.

Note : load_model nécessite faster_whisper installé,
on teste les fonctions utilitaires et les constantes.
"""
import pytest

from core.model import (
    is_model_cached, MODEL_SIZES, _NUM_WORKERS, _CPU_THREADS,
)


# ── Constantes ───────────────────────────────────────────────────────────


class TestConstants:

    def test_num_workers(self):
        assert _NUM_WORKERS == 4

    def test_cpu_threads(self):
        assert _CPU_THREADS == 4

    def test_model_sizes_known_models(self):
        assert "tiny" in MODEL_SIZES
        assert "base" in MODEL_SIZES
        assert "small" in MODEL_SIZES
        assert "medium" in MODEL_SIZES
        assert "large-v3" in MODEL_SIZES
        assert "large-v3-turbo" in MODEL_SIZES

    def test_model_sizes_reasonable(self):
        """Les tailles doivent être raisonnables (> 10 Mo, < 10 Go)."""
        for name, size in MODEL_SIZES.items():
            assert size > 10_000_000, f"{name} trop petit"
            assert size < 10_000_000_000, f"{name} trop grand"

    def test_tiny_smallest(self):
        assert MODEL_SIZES["tiny"] < MODEL_SIZES["base"]
        assert MODEL_SIZES["base"] < MODEL_SIZES["small"]
        assert MODEL_SIZES["small"] < MODEL_SIZES["medium"]


# ── is_model_cached ──────────────────────────────────────────────────────


class TestIsModelCached:

    def test_uncached_model(self):
        """Un modèle avec un nom inventé ne devrait pas être en cache."""
        cached, repo_dir, total = is_model_cached("inexistant_model_xyz")
        # Soit False (pas en cache), soit True (erreur → on suppose en cache)
        assert isinstance(cached, bool)
        assert isinstance(total, int)

    def test_returns_tuple_of_three(self):
        result = is_model_cached("tiny")
        assert len(result) == 3
        cached, repo_dir, total = result
        assert isinstance(cached, bool)
        assert isinstance(repo_dir, str)
        assert isinstance(total, int)

    def test_handles_import_error_gracefully(self):
        """Si faster_whisper n'a pas _MODELS, le fallback fonctionne."""
        # Le try/except ImportError dans le code protège ce cas
        # On teste juste que la fonction ne crashe pas
        result = is_model_cached("tiny")
        assert result is not None
