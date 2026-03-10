# -*- coding: utf-8 -*-
"""
Whisper Hélio — Module d'export multi-format.

Convertit les segments de transcription en différents formats
d'export : SRT, VTT, TXT horodaté, TXT brut, JSON.

Chaque convertisseur est une fonction pure (pas d'effets de bord),
ce qui facilite les tests unitaires et la réutilisation.
"""

from __future__ import annotations

import json
import os
from typing import NamedTuple, Sequence, Tuple, Union

__all__ = [
    "Segment",
    "SegmentLike",
    "EXPORT_FORMATS",
    "export_files",
    "to_srt",
    "to_vtt",
    "to_txt_timestamped",
    "to_txt_plain",
    "to_json_export",
]


# ── Types ────────────────────────────────────────────────────────────────

class Segment(NamedTuple):
    """Un segment de transcription avec ses bornes temporelles."""
    text:  str
    start: float
    end:   float


# Accepte aussi les tuples bruts (text, start, end) — compatible Python 3.8+
SegmentLike = Union[Segment, Tuple[str, float, float]]


# ── Formatage du temps ───────────────────────────────────────────────────

def _decompose(seconds: float) -> Tuple[int, int, int, int]:
    """Décompose un nombre de secondes en (h, m, s, ms)."""
    seconds = max(0.0, seconds)   # clamp négatifs → 0
    total_s = int(seconds)
    ms = int(round((seconds - total_s) * 1000))
    # Éviter ms=1000 dû à l'arrondi
    if ms >= 1000:
        total_s += 1
        ms = 0
    h, remainder = divmod(total_s, 3600)
    m, s = divmod(remainder, 60)
    return h, m, s, ms


def _ts_srt(seconds: float) -> str:
    """HH:MM:SS,mmm (format SubRip)."""
    h, m, s, ms = _decompose(seconds)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ts_vtt(seconds: float) -> str:
    """HH:MM:SS.mmm (format WebVTT)."""
    h, m, s, ms = _decompose(seconds)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _ts_txt(seconds: float) -> str:
    """[HH:MM:SS] (format texte horodaté)."""
    h, m, s, _ms = _decompose(seconds)
    return f"[{h:02d}:{m:02d}:{s:02d}]"


# ── Convertisseurs ───────────────────────────────────────────────────────

def to_srt(segments: Sequence[SegmentLike]) -> str:
    """
    Convertit en format SubRip (.srt).

    >>> to_srt([("Bonjour", 0.0, 1.5)])
    '1\\n00:00:00,000 --> 00:00:01,500\\nBonjour\\n'
    """
    blocks: list[str] = []
    for i, (text, start, end) in enumerate(segments, 1):
        blocks.append(
            f"{i}\n"
            f"{_ts_srt(start)} --> {_ts_srt(end)}\n"
            f"{text}\n"
        )
    return "\n".join(blocks)


def to_vtt(segments: Sequence[SegmentLike]) -> str:
    """
    Convertit en format WebVTT (.vtt).

    Inclut l'en-tête ``WEBVTT`` obligatoire.
    """
    lines: list[str] = ["WEBVTT", ""]
    for i, (text, start, end) in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_ts_vtt(start)} --> {_ts_vtt(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def to_txt_timestamped(segments: Sequence[SegmentLike]) -> str:
    """Convertit en texte avec horodatage [HH:MM:SS] par ligne."""
    return "\n".join(
        f"{_ts_txt(start)} {text}"
        for text, start, _end in segments
    )


def to_txt_plain(segments: Sequence[SegmentLike]) -> str:
    """Convertit en texte brut (sans timestamps)."""
    return "\n".join(text for text, _s, _e in segments)


def to_json_export(
    segments: Sequence[SegmentLike],
    source_file: str = "",
) -> str:
    """
    Convertit en JSON structuré avec métadonnées.

    Inclut : source, nombre de segments, durée totale,
    et la liste détaillée des segments.
    """
    total_duration = max((end for _, _, end in segments), default=0.0)
    data = {
        "source": source_file,
        "segments_count": len(segments),
        "duration_seconds": round(total_duration, 3),
        "segments": [
            {
                "id": i,
                "start": round(start, 3),
                "end": round(end, 3),
                "text": text,
            }
            for i, (text, start, end) in enumerate(segments, 1)
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Table des formats disponibles ────────────────────────────────────────

EXPORT_FORMATS = {
    "srt": {
        "label": "SRT (sous-titres)",
        "ext": ".srt",
        "fn": to_srt,
    },
    "vtt": {
        "label": "VTT (sous-titres web)",
        "ext": ".vtt",
        "fn": to_vtt,
    },
    "txt_ts": {
        "label": "TXT horodaté",
        "ext": "_horodate.txt",
        "fn": to_txt_timestamped,
    },
    "txt": {
        "label": "TXT brut",
        "ext": ".txt",
        "fn": to_txt_plain,
    },
    "json": {
        "label": "JSON",
        "ext": ".json",
        "fn": to_json_export,
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────

def _unique_path(path: str) -> str:
    """Retourne un chemin unique en ajoutant _2, _3... si le fichier existe."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{base}_{n}{ext}"):
        n += 1
    return f"{base}_{n}{ext}"


# ── Export groupé ────────────────────────────────────────────────────────

def export_files(
    segments: Sequence[SegmentLike],
    source_path: str,
    format_keys: Sequence[str],
    source_filename: str = "",
    output_dir: str = "",
) -> list[str]:
    """
    Exporte les segments dans les formats sélectionnés.

    Les fichiers sont créés dans *output_dir* (si fourni) ou dans le
    même dossier que *source_path*, avec le même nom de base et
    l'extension du format choisi.
    Si un fichier existe déjà, un suffixe numéroté est ajouté (_2, _3...).

    SRT et VTT sont écrits en UTF-8 avec BOM pour compatibilité
    Windows (accents français).

    Parameters
    ----------
    segments : liste de (text, start, end)
    source_path : chemin complet du fichier audio source
    format_keys : clés à exporter ("srt", "vtt", "txt_ts", "txt", "json")
    source_filename : nom affiché dans le JSON (optionnel)
    output_dir : dossier de destination (optionnel, défaut = dossier source)

    Returns
    -------
    list[str] : noms des fichiers créés (basename uniquement)

    Raises
    ------
    OSError : si l'écriture d'un fichier échoue
    """
    if not segments or not format_keys:
        return []

    base_dir = output_dir or os.path.dirname(source_path) or "."
    os.makedirs(base_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(source_path))[0]
    created: list[str] = []

    for key in format_keys:
        fmt = EXPORT_FORMATS.get(key)
        if fmt is None:
            continue

        # Générer le contenu
        fn = fmt["fn"]
        if key == "json":
            content = fn(segments, source_filename or os.path.basename(source_path))
        else:
            content = fn(segments)

        # Chemin unique (anti-écrasement)
        out_path = _unique_path(os.path.join(base_dir, base_name + fmt["ext"]))

        # UTF-8 avec BOM pour SRT/VTT (accents français dans les lecteurs Windows)
        encoding = "utf-8-sig" if key in ("srt", "vtt") else "utf-8"
        with open(out_path, "w", encoding=encoding) as f:
            f.write(content)

        created.append(os.path.basename(out_path))

    return created
