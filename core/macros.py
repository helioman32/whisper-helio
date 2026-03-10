"""
core/macros.py — Traitement texte : macros vocales, actions, dictionnaire
Logique pure, zéro dépendance Tkinter.
"""
from __future__ import annotations

import os
import re
import subprocess

from core.config import regex_cache, log_error
from i18n.translations import tr

# ── Recherche programmes (cache local) ─────────────────────────────────────
_office_cache: dict[str, str | None] = {}


def _find_office(app_name: str) -> str | None:
    """Cherche Excel ou Word dans les emplacements Office standard (résultat mis en cache)."""
    key = app_name.upper()
    if key in _office_cache:
        return _office_cache[key]
    candidates = [
        rf"C:\Program Files\Microsoft Office\root\Office16\{app_name}",
        rf"C:\Program Files\Microsoft Office\root\Office15\{app_name}",
        rf"C:\Program Files (x86)\Microsoft Office\root\Office16\{app_name}",
        rf"C:\Program Files (x86)\Microsoft Office\Office16\{app_name}",
        rf"C:\Program Files (x86)\Microsoft Office\Office15\{app_name}",
        rf"C:\Program Files\Microsoft Office\Office16\{app_name}",
    ]
    result = next((p for p in candidates if os.path.exists(p)), None)
    _office_cache[key] = result
    return result


_browser_cache: dict[str, str] = {}


def _find_browser(exe_name: str, *extra_paths: str) -> str:
    """Cherche un navigateur dans les emplacements standards (résultat mis en cache)."""
    key = exe_name.lower()
    if key in _browser_cache:
        return _browser_cache[key]
    candidates = [
        rf"C:\Program Files\{extra_paths[0] if extra_paths else ''}\{exe_name}",
        rf"C:\Program Files (x86)\{extra_paths[0] if extra_paths else ''}\{exe_name}",
    ] if extra_paths else []
    candidates += [rf"C:\Program Files\{exe_name}", rf"C:\Program Files (x86)\{exe_name}"]
    result = next((p for p in candidates if os.path.exists(p)), exe_name)
    _browser_cache[key] = result
    return result


# ── Actions intégrées ──────────────────────────────────────────────────────
# { nom_vocal: (chemin_ou_commande, label_affichage) }
BUILTIN_ACTIONS = {
    "explorateur":  ("explorer.exe",    "Explorateur Windows"),
    "explorer":     ("explorer.exe",    "Explorateur Windows"),
    "bureau":       (["explorer.exe", "shell:Desktop"], "Bureau"),
    "calculatrice": ("calc.exe",        "Calculatrice"),
    "bloc-notes":   ("notepad.exe",     "Bloc-notes"),
    "notepad":      ("notepad.exe",     "Bloc-notes"),
    "taches":       ("taskmgr.exe",     "Gestionnaire de taches"),
    "paint":        ("mspaint.exe",     "Paint"),
    "excel":        (None,              "Excel"),   # chemin résolu dynamiquement
    "word":         (None,              "Word"),    # chemin résolu dynamiquement
    "chrome":       (None,              "Chrome"),
    "firefox":      (None,              "Firefox"),
    "edge":         ("msedge.exe",      "Microsoft Edge"),
}


def _resolve_builtin(name: str):
    """Résout le chemin réel d'une action intégrée."""
    entry = BUILTIN_ACTIONS.get(name.lower())
    if not entry:
        return None, None
    cmd, label = entry
    if cmd is not None:
        return cmd, label
    # Résolution dynamique pour les programmes dont le chemin varie
    n = name.lower()
    if n == "excel":
        path = _find_office("EXCEL.EXE")
        return path or "excel.exe", label   # fallback via PATH
    if n == "word":
        path = _find_office("WINWORD.EXE")
        return path or "winword.exe", label  # fallback via PATH
    if n == "chrome":
        path = _find_browser("chrome.exe", "Google\\Chrome\\Application")
        return path, label   # _find_browser retourne exe_name si introuvable
    if n == "firefox":
        path = _find_browser("firefox.exe", "Mozilla Firefox")
        return path, label
    return None, label


# ── Build caches (appelés paresseusement par apply_*) ─────────────────────

def build_macros_cache(config: dict) -> None:
    """Compile les patterns regex des macros — le NOM est le déclencheur direct."""
    macros = config.get("macros", [])
    if not macros:
        regex_cache["macros"] = []
        return
    entries = []
    for macro in macros:
        name = macro.get("name", "").strip()
        repl = macro.get("text", "")
        if not name:
            continue
        # Le nom peut contenir des espaces ou underscores → on normalise
        name_pattern = re.escape(name.replace("_", " "))
        pat = re.compile(r'\b' + name_pattern + r'\b', re.IGNORECASE)
        entries.append((pat, repl))
    regex_cache["macros"] = entries


def apply_macros(text: str, config: dict) -> str:
    """Remplace les macros vocales dans le texte transcrit."""
    if not text:
        return text
    entries = regex_cache["macros"]
    if entries is None:
        build_macros_cache(config)
        entries = regex_cache["macros"] or []
    if not entries:
        return text
    result = text
    for pat, repl in entries:
        result = pat.sub(lambda _: repl, result)   # lambda évite l'interprétation des backslashes
    return result


def build_actions_cache(config: dict) -> None:
    """Compile les patterns regex des actions (mis en cache)."""
    trigger = config.get("action_trigger", "action").lower().strip()
    if not trigger:
        regex_cache["actions"] = []
        return
    all_actions = {}
    for name in BUILTIN_ACTIONS:
        all_actions[name] = ("builtin", name)
    for act in config.get("actions", []):
        name = act.get("name", "").lower().strip()
        path = act.get("path", "").strip()
        if name and path:
            all_actions[name] = ("custom", path)
    entries = []
    for name, (kind, value) in all_actions.items():
        # Normaliser underscores → espaces (Whisper transcrit avec espaces)
        name_pattern = re.escape(name.replace("_", " "))
        pat = re.compile(r'\b' + re.escape(trigger) + r'\s+' + name_pattern + r'\b', re.IGNORECASE)
        entries.append((pat, name, kind, value))
    regex_cache["actions"] = entries


def apply_actions(text: str, config: dict, set_status=None) -> str:
    """Détecte et exécute les actions vocales. Retourne le texte nettoyé.

    set_status(text, color_dot, color_text) — callback optionnel pour afficher
    le statut dans l'interface (remplace l'ancien appel direct à set_statut_safe).
    """
    if not text:
        return text
    entries = regex_cache["actions"]
    if entries is None:
        build_actions_cache(config)
        entries = regex_cache["actions"] or []
    if not entries:
        return text

    _COLOR_ORANGE = "#f39c12"
    _COLOR_GREEN  = "#2ecc71"

    result = text
    for pat, name, kind, value in entries:
        if not pat.search(result):
            continue
        launched     = False
        display_name = name  # valeur par défaut
        try:
            if kind == "builtin":
                cmd, label = _resolve_builtin(name)
                display_name = label or name
                if cmd:
                    subprocess.Popen(cmd if isinstance(cmd, list) else [cmd])
                    launched = True
                elif set_status:
                    set_status(tr("action_not_found", name=display_name), _COLOR_ORANGE, _COLOR_ORANGE)
            else:  # custom
                # Sécurité : accepter uniquement les .exe locaux (pas de .bat/.cmd/.vbs/UNC)
                # realpath résout les .., symlinks, et chemins relatifs déguisés
                _real_path = os.path.realpath(value)
                _val_lower = _real_path.lower()
                _is_safe = (
                    _val_lower.endswith('.exe')
                    and not _real_path.startswith('\\\\')  # bloquer UNC \\serveur\...
                    and not _real_path.startswith('//')     # bloquer UNC //serveur/...
                    and os.path.isabs(_real_path)           # chemin absolu obligatoire
                    and os.path.isfile(_real_path)          # isfile (pas isdir)
                )
                if _is_safe:
                    subprocess.Popen([_real_path])
                    launched = True
                elif set_status:
                    set_status(tr("action_not_found", name=display_name), _COLOR_ORANGE, _COLOR_ORANGE)
            if launched and set_status:
                set_status(tr("action_launched", name=display_name), _COLOR_GREEN, _COLOR_GREEN)
        except Exception as e:
            log_error(e)
        if launched:
            result = pat.sub("", result).strip()
    return result


def build_dictionary_cache(config: dict) -> None:
    """Compile les patterns regex du dictionnaire (mis en cache)."""
    dictionary = config.get("dictionary", [])
    if not dictionary:
        regex_cache["dictionary"] = []
        return
    entries = []
    for entry in dictionary:
        wrong   = entry.get("wrong", "").strip()
        correct = entry.get("correct", "")
        if not wrong:
            continue
        pat = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)
        entries.append((pat, correct))
    regex_cache["dictionary"] = entries


def apply_dictionary(text: str, config: dict) -> str:
    """Corrige les mots mal transcrits par Whisper via le dictionnaire utilisateur."""
    if not text:
        return text
    entries = regex_cache["dictionary"]
    if entries is None:
        build_dictionary_cache(config)
        entries = regex_cache["dictionary"] or []
    if not entries:
        return text
    result = text
    for pat, repl in entries:
        result = pat.sub(lambda _: repl, result)   # lambda évite l'interprétation des backslashes
    return result
