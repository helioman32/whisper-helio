"""
Tests pour core/macros.py — macros vocales, actions, dictionnaire.
"""
import pytest

from core.config import regex_cache, invalidate_regex_cache
from core.macros import (
    apply_macros, apply_actions, apply_dictionary,
    build_macros_cache, build_actions_cache, build_dictionary_cache,
    BUILTIN_ACTIONS, _find_office, _find_browser, _resolve_builtin,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Invalide le cache avant chaque test."""
    invalidate_regex_cache()
    yield
    invalidate_regex_cache()


# ── apply_macros ─────────────────────────────────────────────────────────


class TestApplyMacros:

    def test_simple_replacement(self, sample_config):
        result = apply_macros("Envoi cordialement", sample_config)
        assert "Cordialement,\nHélio" in result

    def test_no_macros(self, default_config):
        result = apply_macros("Bonjour le monde", default_config)
        assert result == "Bonjour le monde"

    def test_empty_text(self, sample_config):
        result = apply_macros("", sample_config)
        assert result == ""

    def test_case_insensitive(self, sample_config):
        result = apply_macros("Envoi CORDIALEMENT", sample_config)
        assert "Hélio" in result

    def test_multiple_macros(self, sample_config):
        result = apply_macros("cordialement et date du jour", sample_config)
        assert "Hélio" in result
        assert "10 mars 2026" in result

    def test_word_boundary(self):
        """La macro ne doit pas remplacer un sous-mot."""
        config = {
            "macros": [{"name": "test", "text": "REPLACED"}],
        }
        # "test" doit être remplacé, mais pas "testing"
        result = apply_macros("test ok", config)
        assert "REPLACED" in result
        invalidate_regex_cache()
        result2 = apply_macros("testing ok", config)
        # "testing" contient "test" mais la frontière \b devrait empêcher le remplacement
        # Note: \btest\b ne matche pas "testing" — correct
        assert "REPLACED" not in result2

    def test_race_condition_safety(self, sample_config):
        """Le cache peut être invalidé entre le test et la lecture — fallback or []."""
        # Simule la situation : cache valide puis invalidé
        build_macros_cache(sample_config)
        assert regex_cache["macros"] is not None
        # Invalider pendant l'utilisation
        invalidate_regex_cache()
        # apply_macros ne doit pas crasher même si le cache est None
        result = apply_macros("cordialement", sample_config)
        assert "Hélio" in result  # rebuild automatique


# ── apply_dictionary ─────────────────────────────────────────────────────


class TestApplyDictionary:

    def test_simple_correction(self, sample_config):
        result = apply_dictionary("bonjour elio", sample_config)
        assert "Hélio" in result

    def test_case_insensitive(self, sample_config):
        result = apply_dictionary("WHISPER est super", sample_config)
        assert "Whisper" in result

    def test_no_dictionary(self, default_config):
        result = apply_dictionary("hello world", default_config)
        assert result == "hello world"

    def test_empty_text(self, sample_config):
        assert apply_dictionary("", sample_config) == ""

    def test_multiple_corrections(self, sample_config):
        result = apply_dictionary("elio utilise whisper", sample_config)
        assert "Hélio" in result
        assert "Whisper" in result


# ── apply_actions ────────────────────────────────────────────────────────


class TestApplyActions:

    def test_builtin_action_detected(self, default_config):
        """L'action 'action calculatrice' doit être détectée."""
        build_actions_cache(default_config)
        entries = regex_cache["actions"]
        # Vérifier qu'il y a des patterns
        assert len(entries) > 0
        # Vérifier que "calculatrice" est dans les actions
        names = [name for _, name, _, _ in entries]
        assert "calculatrice" in names

    def test_action_removed_from_text(self, default_config):
        """Le texte de l'action doit être supprimé du résultat."""
        # On ne peut pas tester le lancement réel de l'exe en tests
        # Mais on peut vérifier le pattern matching
        build_actions_cache(default_config)
        entries = regex_cache["actions"]
        calc_pattern = None
        for pat, name, kind, value in entries:
            if name == "calculatrice":
                calc_pattern = pat
                break
        assert calc_pattern is not None
        assert calc_pattern.search("action calculatrice")

    def test_empty_text(self, default_config):
        result = apply_actions("", default_config)
        assert result == ""

    def test_no_action_trigger(self):
        config = {"action_trigger": "", "actions": []}
        build_actions_cache(config)
        assert regex_cache["actions"] == []

    def test_custom_trigger(self):
        config = {
            "action_trigger": "lance",
            "actions": [],
        }
        build_actions_cache(config)
        entries = regex_cache["actions"]
        # Les builtins doivent utiliser "lance" comme trigger
        calc_pat = None
        for pat, name, _, _ in entries:
            if name == "calculatrice":
                calc_pat = pat
                break
        assert calc_pat is not None
        assert calc_pat.search("lance calculatrice")
        assert not calc_pat.search("action calculatrice")


# ── BUILTIN_ACTIONS ──────────────────────────────────────────────────────


class TestBuiltinActions:

    def test_all_builtins_have_label(self):
        for name, (cmd, label) in BUILTIN_ACTIONS.items():
            assert isinstance(label, str)
            assert len(label) > 0

    def test_resolve_builtin_known(self):
        cmd, label = _resolve_builtin("calculatrice")
        assert cmd == "calc.exe"
        assert label == "Calculatrice"

    def test_resolve_builtin_unknown(self):
        cmd, label = _resolve_builtin("inconnu")
        assert cmd is None
        assert label is None

    def test_resolve_explorer(self):
        cmd, label = _resolve_builtin("explorateur")
        assert cmd == "explorer.exe"


# ── build caches ─────────────────────────────────────────────────────────


class TestBuildCaches:

    def test_build_macros_empty(self):
        config = {"macros": []}
        build_macros_cache(config)
        assert regex_cache["macros"] == []

    def test_build_macros_skips_empty_names(self):
        config = {"macros": [
            {"name": "", "text": "val"},
            {"name": "ok", "text": "val"},
        ]}
        build_macros_cache(config)
        assert len(regex_cache["macros"]) == 1

    def test_build_dictionary_empty(self):
        config = {"dictionary": []}
        build_dictionary_cache(config)
        assert regex_cache["dictionary"] == []

    def test_build_dictionary_skips_empty_wrong(self):
        config = {"dictionary": [
            {"wrong": "", "correct": "val"},
            {"wrong": "ok", "correct": "val"},
        ]}
        build_dictionary_cache(config)
        assert len(regex_cache["dictionary"]) == 1
