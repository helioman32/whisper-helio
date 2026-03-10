"""
Fixtures partagées pour les tests Whisper Hélio.
"""
import os
import sys
import json
import tempfile

import pytest

# Ajouter le dossier racine au PYTHONPATH
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


@pytest.fixture
def tmp_config_file(tmp_path):
    """Retourne un chemin temporaire pour un fichier config."""
    return str(tmp_path / "test_config.json")


@pytest.fixture
def tmp_log_file(tmp_path):
    """Retourne un chemin temporaire pour un fichier log."""
    return str(tmp_path / "test_crash.log")


@pytest.fixture
def default_config():
    """Retourne une copie de la config par défaut."""
    from core.config import DEFAULT_CONFIG
    return DEFAULT_CONFIG.copy()


@pytest.fixture
def sample_config(default_config):
    """Config avec des macros, actions et dictionnaire."""
    default_config["macros"] = [
        {"name": "cordialement", "text": "Cordialement,\nHélio"},
        {"name": "date du jour", "text": "10 mars 2026"},
    ]
    default_config["actions"] = [
        {"name": "test_app", "path": "C:\\Windows\\notepad.exe"},
    ]
    default_config["dictionary"] = [
        {"wrong": "whisper", "correct": "Whisper"},
        {"wrong": "elio", "correct": "Hélio"},
    ]
    return default_config
