"""
core/transcription.py — Transcription Whisper + copier/coller intelligent.
Zéro dépendance Tkinter, zéro global.
"""
from __future__ import annotations

import gc
import time
from typing import Callable, Optional

import pyautogui
import pyperclip

from core.audio import MIN_AUDIO_SAMPLES, SAMPLE_RATE, VAD_THRESHOLD, has_voice
from core.config import log_error
from core.hotkeys import send_ctrl_v


# ── Transcription ────────────────────────────────────────────────────────

def transcribe_audio(
    model,
    audio_data,
    config: dict,
    device: str = "cpu",
    compute: str = "int8",
    use_vad: bool = True,
) -> str:
    """Transcrit un tableau numpy en texte.

    Parameters
    ----------
    model : WhisperModel chargé
    audio_data : np.ndarray float32
    config : dict avec clé "language"
    device / compute : pour le logging
    use_vad : True pour filtrer le silence via has_voice()
    """
    if len(audio_data) < MIN_AUDIO_SAMPLES:
        log_error(msg=f"[SKIP] Audio trop court: {len(audio_data)} samples "
                      f"(min={MIN_AUDIO_SAMPLES}, soit {MIN_AUDIO_SAMPLES/SAMPLE_RATE:.1f}s)")
        return ""

    # Skip si silence (VAD)
    if use_vad and not has_voice(audio_data):
        _dur = len(audio_data) / SAMPLE_RATE
        log_error(msg=f"[SKIP] VAD silence détecté ({_dur:.1f}s audio, seuil={VAD_THRESHOLD})")
        return ""

    _t0 = time.perf_counter()
    try:
        gc.disable()   # évite les pauses GC pendant l'inférence
        segments, _ = model.transcribe(
            audio_data,
            language=config["language"],
            beam_size=1,
            best_of=1,
            temperature=(0, 0.2, 0.4),  # 3-pass voting
            condition_on_previous_text=False,
            without_timestamps=True,
            no_speech_threshold=0.55,
            vad_filter=False,   # onnxruntime exclu du build — notre has_voice() filtre déjà
        )
        result = " ".join(s.text.strip() for s in segments).strip()
        _elapsed = time.perf_counter() - _t0
        _dur = len(audio_data) / SAMPLE_RATE
        log_error(msg=f"[PERF] Transcription: {_elapsed:.2f}s pour {_dur:.1f}s audio "
                      f"({device}/{compute}) ratio={_elapsed/_dur:.2f}x")
        return result
    except Exception as e:
        log_error(e, f"Transcription échouée (device={device})")
        return ""
    finally:
        gc.enable()


# ── Copie et collage ─────────────────────────────────────────────────────

def fast_copy(text: str) -> bool:
    """Copie le texte dans le presse-papier. Retourne True si réussi."""
    try:
        pyperclip.copy(text)
        return True
    except Exception as e:
        log_error(e, "fast_copy: presse-papier verrouillé")
        return False


def paste_text() -> None:
    """Colle le texte depuis le presse-papier via keybd_event (zéro hook)."""
    try:
        send_ctrl_v()
    except Exception:
        try:
            pyautogui.hotkey("ctrl", "v")
        except Exception as e2:
            log_error(e2, "paste_text: les deux méthodes ont échoué")


_last_pasted_text = [""]   # dernier texte collé — pour l'espace intelligent


def copy_and_paste(
    text: str,
    delay: float = 0.05,
    restore_focus_fn: Optional[Callable[[], bool]] = None,
    target_hwnd: int = 0,
) -> None:
    """Copie et colle le texte avec espace intelligent avant le texte.

    Parameters
    ----------
    text : texte à coller
    delay : délai avant collage si pas de fenêtre cible
    restore_focus_fn : callback() → bool qui restaure le focus
    target_hwnd : HWND de la fenêtre cible (pour logging)
    """
    if not text:
        return

    # Espace intelligent basé sur le dernier texte qu'on a collé
    prefix = ""
    prev = _last_pasted_text[0]
    if prev:
        last = prev[-1]
        if last.isalnum() or last in ".!?:;,)»\"'":
            prefix = " "

    final_text = prefix + text

    # Sauvegarder le presse-papier utilisateur avant de l'écraser
    old_clipboard = None
    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass

    # Copier avec retry si clipboard verrouillé
    if not fast_copy(final_text):
        time.sleep(0.05)
        if not fast_copy(final_text):
            log_error(msg="[PASTE] Clipboard verrouillé après retry — texte perdu")
            return

    # Restaurer le focus sur la fenêtre cible avant de coller
    if restore_focus_fn and restore_focus_fn():
        # 80ms : minimum empirique pour que Windows traite le changement de focus
        time.sleep(0.08)
    else:
        if restore_focus_fn is not None:
            log_error(msg=f"[PASTE] Focus non restauré (target_hwnd={target_hwnd})")
        # Délai standard si pas de fenêtre cible connue
        if delay > 0:
            time.sleep(delay)
    paste_text()
    _last_pasted_text[0] = text   # mémoriser le texte brut (sans prefix)

    # Restaurer le presse-papier original après collage
    if old_clipboard is not None:
        time.sleep(0.08)
        try:
            current_cb = pyperclip.paste()
        except Exception:
            current_cb = None
        if current_cb is not None and current_cb == final_text:
            for _attempt in range(2):
                try:
                    pyperclip.copy(old_clipboard)
                    break
                except Exception:
                    time.sleep(0.1)   # clipboard verrouillé — réessayer une fois
            else:
                log_error(msg="[PASTE] Clipboard restore échoué après 2 tentatives")
