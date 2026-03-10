"""
Tests pour core/system.py — dpi_scale, screen_scale, fit_window.
"""
import sys
import pytest

from core.system import dpi_scale, screen_scale, fit_window
from core.config import MIN_W, MIN_H


# ── dpi_scale ────────────────────────────────────────────────────────────


class TestDpiScale:

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_returns_float(self):
        result = dpi_scale()
        assert isinstance(result, float)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_at_least_1(self):
        assert dpi_scale() >= 1.0

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_reasonable_range(self):
        """Le DPI scale doit être entre 1.0 et 4.0."""
        result = dpi_scale()
        assert 1.0 <= result <= 4.0


# ── screen_scale ─────────────────────────────────────────────────────────


class TestScreenScale:

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_returns_float(self):
        result = screen_scale()
        assert isinstance(result, float)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_between_0_and_1(self):
        result = screen_scale()
        assert 0.0 < result <= 1.0


# ── fit_window ───────────────────────────────────────────────────────────


class TestFitWindow:

    def test_normal_window(self):
        w, h = fit_window(800, 600, 1920, 1080)
        assert w == 800
        assert h == 600

    def test_too_wide(self):
        w, h = fit_window(2000, 600, 1920, 1080)
        assert w == 1920 - 40  # sw - margin
        assert h == 600

    def test_too_tall(self):
        w, h = fit_window(800, 1200, 1920, 1080)
        assert w == 800
        assert h == 1080 - 40

    def test_both_too_large(self):
        w, h = fit_window(3000, 2000, 1920, 1080)
        assert w <= 1920
        assert h <= 1080

    def test_minimum_enforced(self):
        w, h = fit_window(100, 50, 1920, 1080)
        assert w >= MIN_W
        assert h >= MIN_H

    def test_small_screen(self):
        """Sur un très petit écran, les minimums sont respectés."""
        w, h = fit_window(800, 600, 640, 480)
        assert w >= MIN_W
        assert h >= MIN_H

    def test_custom_margin(self):
        w, h = fit_window(1900, 600, 1920, 1080, margin=100)
        assert w == 1920 - 100
