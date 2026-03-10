"""
Tests pour i18n/translations.py — traductions, cache, provider.
"""
import pytest

from i18n.translations import (
    TRANSLATIONS, tr, set_lang_provider, clear_cache,
)


# ── TRANSLATIONS structure ───────────────────────────────────────────────


class TestTranslationsStructure:

    def test_three_languages(self):
        assert "fr" in TRANSLATIONS
        assert "en" in TRANSLATIONS
        assert "de" in TRANSLATIONS

    def test_all_languages_have_same_keys(self):
        """Toutes les langues doivent avoir les mêmes clés."""
        fr_keys = set(TRANSLATIONS["fr"].keys())
        en_keys = set(TRANSLATIONS["en"].keys())
        de_keys = set(TRANSLATIONS["de"].keys())

        missing_en = fr_keys - en_keys
        missing_de = fr_keys - de_keys

        assert not missing_en, f"Clés manquantes en EN: {missing_en}"
        assert not missing_de, f"Clés manquantes en DE: {missing_de}"

    def test_no_empty_values(self):
        """Aucune traduction ne doit être vide."""
        for lang, translations in TRANSLATIONS.items():
            for key, value in translations.items():
                assert value.strip() != "", f"{lang}.{key} est vide"


# ── tr() ─────────────────────────────────────────────────────────────────


class TestTr:

    def setup_method(self):
        clear_cache()
        set_lang_provider(lambda: "fr")

    def test_simple_key(self):
        result = tr("title")
        assert "Whisper" in result

    def test_with_placeholder(self):
        result = tr("ready", hotkey="F9")
        assert "F9" in result

    def test_missing_key_returns_key(self):
        result = tr("nonexistent_key_xyz")
        assert result == "nonexistent_key_xyz"

    def test_english(self):
        set_lang_provider(lambda: "en")
        clear_cache()
        result = tr("title")
        assert "Whisper" in result

    def test_german(self):
        set_lang_provider(lambda: "de")
        clear_cache()
        result = tr("title")
        assert "Whisper" in result

    def test_unknown_language_fallback_fr(self):
        set_lang_provider(lambda: "xx")
        clear_cache()
        result = tr("title")
        assert "Whisper" in result  # fallback FR

    def test_cache_works(self):
        """Deux appels avec la même clé utilisent le cache."""
        r1 = tr("title")
        r2 = tr("title")
        assert r1 == r2

    def test_clear_cache(self):
        tr("title")
        clear_cache()
        # Pas de crash après clear
        result = tr("title")
        assert "Whisper" in result

    def teardown_method(self):
        clear_cache()
        set_lang_provider(lambda: "fr")
