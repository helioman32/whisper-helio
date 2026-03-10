"""
Tests pour core/export.py — convertisseurs SRT/VTT/TXT/JSON + export_files.
"""
import json
import os

import pytest

from core.export import (
    Segment, to_srt, to_vtt, to_txt_timestamped, to_txt_plain,
    to_json_export, export_files, EXPORT_FORMATS, _decompose, _unique_path,
)


# ── Données de test ──────────────────────────────────────────────────────

SEGMENTS = [
    Segment("Bonjour le monde", 0.0, 2.5),
    Segment("Comment ça va ?", 3.1, 5.8),
    Segment("Très bien merci", 6.0, 8.0),
]

SINGLE = [Segment("Test", 0.0, 1.0)]
EMPTY = []


# ── _decompose ───────────────────────────────────────────────────────────


class TestDecompose:

    def test_zero(self):
        assert _decompose(0.0) == (0, 0, 0, 0)

    def test_simple_seconds(self):
        assert _decompose(5.5) == (0, 0, 5, 500)

    def test_minutes(self):
        assert _decompose(125.75) == (0, 2, 5, 750)

    def test_hours(self):
        assert _decompose(3661.1) == (1, 1, 1, 100)

    def test_negative_clamped(self):
        assert _decompose(-5.0) == (0, 0, 0, 0)

    def test_ms_rounding_edge(self):
        # 59.9999 → ms arrondi pourrait donner 1000
        h, m, s, ms = _decompose(59.9999)
        assert ms < 1000


# ── to_srt ───────────────────────────────────────────────────────────────


class TestToSrt:

    def test_single_segment(self):
        result = to_srt(SINGLE)
        assert "1\n" in result
        assert "00:00:00,000 --> 00:00:01,000" in result
        assert "Test" in result

    def test_multiple_segments(self):
        result = to_srt(SEGMENTS)
        assert "1\n" in result
        assert "2\n" in result
        assert "3\n" in result
        assert "Bonjour le monde" in result
        assert "Comment ça va ?" in result

    def test_empty(self):
        assert to_srt(EMPTY) == ""

    def test_comma_separator(self):
        """SRT utilise la virgule comme séparateur de ms."""
        result = to_srt(SINGLE)
        assert "00:00:00,000" in result  # virgule, pas point


# ── to_vtt ───────────────────────────────────────────────────────────────


class TestToVtt:

    def test_header(self):
        result = to_vtt(SINGLE)
        assert result.startswith("WEBVTT")

    def test_dot_separator(self):
        """VTT utilise le point comme séparateur de ms."""
        result = to_vtt(SINGLE)
        assert "00:00:00.000" in result  # point, pas virgule

    def test_multiple_segments(self):
        result = to_vtt(SEGMENTS)
        lines = result.split("\n")
        assert lines[0] == "WEBVTT"
        assert "Bonjour le monde" in result

    def test_empty(self):
        result = to_vtt(EMPTY)
        assert result.startswith("WEBVTT")


# ── to_txt_timestamped ───────────────────────────────────────────────────


class TestToTxtTimestamped:

    def test_format(self):
        result = to_txt_timestamped(SINGLE)
        assert result.startswith("[00:00:00]")
        assert "Test" in result

    def test_multiple(self):
        result = to_txt_timestamped(SEGMENTS)
        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0].startswith("[00:00:00]")
        assert lines[1].startswith("[00:00:03]")


# ── to_txt_plain ─────────────────────────────────────────────────────────


class TestToTxtPlain:

    def test_no_timestamps(self):
        result = to_txt_plain(SEGMENTS)
        assert "[" not in result
        assert "-->" not in result

    def test_content(self):
        result = to_txt_plain(SEGMENTS)
        lines = result.split("\n")
        assert lines[0] == "Bonjour le monde"
        assert len(lines) == 3


# ── to_json_export ───────────────────────────────────────────────────────


class TestToJsonExport:

    def test_valid_json(self):
        result = to_json_export(SEGMENTS, "test.mp3")
        data = json.loads(result)
        assert data["source"] == "test.mp3"
        assert data["segments_count"] == 3
        assert isinstance(data["duration_seconds"], float)

    def test_segments_structure(self):
        result = to_json_export(SEGMENTS)
        data = json.loads(result)
        seg = data["segments"][0]
        assert "id" in seg
        assert "start" in seg
        assert "end" in seg
        assert "text" in seg
        assert seg["id"] == 1
        assert seg["text"] == "Bonjour le monde"

    def test_unicode_preserved(self):
        segs = [Segment("Hélio — ça marche !", 0.0, 1.0)]
        result = to_json_export(segs)
        assert "Hélio" in result
        assert "ça" in result


# ── _unique_path ─────────────────────────────────────────────────────────


class TestUniquePath:

    def test_no_conflict(self, tmp_path):
        path = str(tmp_path / "test.srt")
        assert _unique_path(path) == path

    def test_with_conflict(self, tmp_path):
        path = str(tmp_path / "test.srt")
        open(path, "w").close()  # créer le fichier
        result = _unique_path(path)
        assert result.endswith("test_2.srt")

    def test_multiple_conflicts(self, tmp_path):
        for i in ["", "_2", "_3"]:
            open(str(tmp_path / f"test{i}.srt"), "w").close()
        result = _unique_path(str(tmp_path / "test.srt"))
        assert result.endswith("test_4.srt")


# ── export_files ─────────────────────────────────────────────────────────


class TestExportFiles:

    def test_export_srt(self, tmp_path):
        source = str(tmp_path / "audio.mp3")
        open(source, "w").close()
        created = export_files(SEGMENTS, source, ["srt"])
        assert len(created) == 1
        assert created[0].endswith(".srt")
        content = open(str(tmp_path / created[0]), encoding="utf-8-sig").read()
        assert "Bonjour le monde" in content

    def test_export_multiple_formats(self, tmp_path):
        source = str(tmp_path / "audio.mp3")
        open(source, "w").close()
        created = export_files(SEGMENTS, source, ["srt", "vtt", "txt", "json"])
        assert len(created) == 4

    def test_export_to_custom_dir(self, tmp_path):
        source = str(tmp_path / "audio.mp3")
        out_dir = str(tmp_path / "exports")
        open(source, "w").close()
        created = export_files(SEGMENTS, source, ["txt"], output_dir=out_dir)
        assert len(created) == 1
        assert os.path.exists(os.path.join(out_dir, created[0]))

    def test_export_creates_output_dir(self, tmp_path):
        source = str(tmp_path / "audio.mp3")
        out_dir = str(tmp_path / "new_folder" / "sub")
        open(source, "w").close()
        created = export_files(SEGMENTS, source, ["txt"], output_dir=out_dir)
        assert os.path.isdir(out_dir)

    def test_export_empty_segments(self, tmp_path):
        source = str(tmp_path / "audio.mp3")
        created = export_files([], source, ["srt"])
        assert created == []

    def test_export_empty_formats(self, tmp_path):
        source = str(tmp_path / "audio.mp3")
        created = export_files(SEGMENTS, source, [])
        assert created == []

    def test_export_invalid_format_ignored(self, tmp_path):
        source = str(tmp_path / "audio.mp3")
        open(source, "w").close()
        created = export_files(SEGMENTS, source, ["srt", "invalid_format"])
        assert len(created) == 1  # seul srt est créé

    def test_export_utf8_bom_srt(self, tmp_path):
        """SRT doit être en UTF-8 avec BOM."""
        source = str(tmp_path / "audio.mp3")
        open(source, "w").close()
        export_files(SEGMENTS, source, ["srt"])
        raw = open(str(tmp_path / "audio.srt"), "rb").read()
        assert raw[:3] == b"\xef\xbb\xbf"  # UTF-8 BOM

    def test_export_anti_overwrite(self, tmp_path):
        """Si un fichier existe, un suffixe numéroté est ajouté."""
        source = str(tmp_path / "audio.mp3")
        open(source, "w").close()
        export_files(SEGMENTS, source, ["txt"])
        export_files(SEGMENTS, source, ["txt"])  # 2ème export
        files = [f for f in os.listdir(tmp_path) if f.endswith(".txt")]
        assert len(files) == 2
