"""
File transcription UI — file chooser, result window, export dialog, macros window.

Heavy dependencies (model, audio state) are passed via callbacks/parameters.
All shared references are accessed via ``ui.*`` (late binding).
"""
from __future__ import annotations

import gc
import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

import pyperclip

import ui
from ui import (
    COLOR_BLUE, COLOR_BLUE_DARK, COLOR_RED, COLOR_RED_DARK,
    COLOR_GREEN, COLOR_GREEN_HOVER, COLOR_ORANGE, COLOR_PURPLE,
    COLOR_WHITE, COLOR_GREY_HOVER, COLOR_SAVE, COLOR_SAVE_HOVER,
    PILL_H, PILL_H_LG, PILL_FONT, PILL_FONT_LG,
)
from ui.helpers import (
    _create_pill_button, _finalize_toplevel, _bind_toplevel_drag,
    _make_scroll_area,
)
from core.export import EXPORT_FORMATS, export_files


# ─────────────────────────────────────────────────────────────────────────
# Audio extensions
# ─────────────────────────────────────────────────────────────────────────

_AUDIO_EXTENSIONS = (
    "*.mp3", "*.wav", "*.flac", "*.ogg", "*.m4a",
    "*.wma", "*.aac", "*.webm", "*.opus", "*.mp4",
)
_AUDIO_EXT_SET = {e.replace("*", "") for e in _AUDIO_EXTENSIONS}


# ─────────────────────────────────────────────────────────────────────────
# Formatting
# ─────────────────────────────────────────────────────────────────────────

_PAUSE_PARAGRAPH = 1.5
_PAUSE_SENTENCE  = 0.8
_SENTENCE_ENDS   = frozenset(".!?…»\")")


def _format_transcription(segments_data):
    """Met en forme le texte transcrit avec paragraphes automatiques."""
    if not segments_data:
        return ""
    paragraphs = []
    current_para = [segments_data[0][0]]
    for i in range(1, len(segments_data)):
        prev_text, _, prev_end = segments_data[i - 1]
        curr_text, curr_start, _ = segments_data[i]
        pause = max(0.0, curr_start - prev_end)
        new_para = False
        if pause >= _PAUSE_PARAGRAPH:
            new_para = True
        elif pause >= _PAUSE_SENTENCE and prev_text and prev_text[-1] in _SENTENCE_ENDS:
            new_para = True
        if new_para:
            paragraphs.append(" ".join(current_para))
            current_para = [curr_text]
        else:
            current_para.append(curr_text)
    if current_para:
        paragraphs.append(" ".join(current_para))
    formatted = []
    for para in paragraphs:
        para = para.strip()
        if para and para[0].islower():
            para = para[0].upper() + para[1:]
        formatted.append(para)
    return "\n\n".join(formatted).strip()


# ─────────────────────────────────────────────────────────────────────────
# Shared state for file transcription (set via init_file_state())
# ─────────────────────────────────────────────────────────────────────────

_last_file_segments = [None]
_last_file_path     = [None]
_file_transcribing  = threading.Lock()
_HAS_BATCHED        = [None]

# Runtime deps set by dictee.pyw
_global_model   = None   # [None] list ref
_is_recording   = None   # threading.Event ref
_mode_libre     = None   # [False] list ref
_detected_device = "cpu"
_file_initial_prompts = {}


def init_file_state(*, global_model, is_recording, mode_libre,
                    detected_device, file_initial_prompts):
    """Set runtime state references for file transcription."""
    global _global_model, _is_recording, _mode_libre
    global _detected_device, _file_initial_prompts
    _global_model = global_model
    _is_recording = is_recording
    _mode_libre = mode_libre
    _detected_device = detected_device
    _file_initial_prompts = file_initial_prompts


# ─────────────────────────────────────────────────────────────────────────
# Drag-and-drop
# ─────────────────────────────────────────────────────────────────────────

def setup_drag_drop(has_dnd, DND_FILES_const):
    """Active le drag-and-drop de fichiers audio via tkinterdnd2."""
    if not has_dnd:
        return
    try:
        ui.root.drop_target_register(DND_FILES_const)
        ui.root.dnd_bind("<<Drop>>", _on_tkdnd_drop)
    except Exception:
        pass


def _on_tkdnd_drop(event):
    """Callback tkinterdnd2."""
    if ui._app_closing[0]:
        return
    raw = event.data
    if not raw or not raw.strip():
        return
    raw = raw.strip()
    if raw.startswith("{"):
        end = raw.find("}")
        filepath = raw[1:end] if end > 0 else raw[1:]
    else:
        if os.path.isfile(raw.replace("/", os.sep)):
            filepath = raw
        else:
            filepath = raw.split()[0]
    filepath = os.path.realpath(filepath.replace("/", os.sep))
    _handle_dropped_file(filepath)


def _handle_dropped_file(filepath):
    """Traite un fichier déposé par drag-and-drop."""
    if ui._app_closing[0]:
        return
    if not os.path.isfile(filepath):
        return
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in _AUDIO_EXT_SET:
        ui.set_statut_safe(ui.tr("file_bad_format", ext=ext), COLOR_ORANGE, COLOR_ORANGE)
        return
    if not _file_transcribing.acquire(blocking=False):
        ui.set_statut_safe(ui.tr("file_busy_file"), COLOR_ORANGE, COLOR_ORANGE)
        return
    if _global_model[0] is None:
        _file_transcribing.release()
        ui.set_statut_safe(ui.tr("file_no_model"), COLOR_RED, COLOR_RED)
        return
    if _is_recording.is_set() or _mode_libre[0]:
        _file_transcribing.release()
        ui.set_statut_safe(ui.tr("file_busy_recording"), COLOR_ORANGE, COLOR_ORANGE)
        return
    filename = os.path.basename(filepath)
    ui.set_statut_safe(ui.tr("file_transcribing", name=filename[:30]), COLOR_BLUE, COLOR_BLUE)
    try:
        threading.Thread(target=_transcribe_file_worker, args=(filepath, filename),
                         daemon=True).start()
    except Exception:
        _file_transcribing.release()


# ─────────────────────────────────────────────────────────────────────────
# File chooser
# ─────────────────────────────────────────────────────────────────────────

def open_file_transcribe():
    """Ouvre un dialogue de sélection de fichier audio et lance la transcription."""
    if not _file_transcribing.acquire(blocking=False):
        ui.set_statut_safe(ui.tr("file_busy_file"), COLOR_ORANGE, COLOR_ORANGE)
        return
    if _global_model[0] is None:
        _file_transcribing.release()
        ui.set_statut_safe(ui.tr("file_no_model"), COLOR_RED, COLOR_RED)
        return
    if _is_recording.is_set() or _mode_libre[0]:
        _file_transcribing.release()
        ui.set_statut_safe(ui.tr("file_busy_recording"), COLOR_ORANGE, COLOR_ORANGE)
        return

    ui.root.attributes("-topmost", False)
    try:
        filepath = filedialog.askopenfilename(
            parent=ui.root,
            title=ui.tr("file_transcribe"),
            filetypes=[
                (ui.tr("file_formats"), " ".join(_AUDIO_EXTENSIONS)),
                ("MP3", "*.mp3"), ("WAV", "*.wav"), ("FLAC", "*.flac"),
                ("OGG/Opus", "*.ogg *.opus"), ("M4A/AAC", "*.m4a *.aac"),
                (ui.tr("file_all_types"), "*.*"),
            ]
        )
    except Exception:
        _file_transcribing.release()
        return
    finally:
        ui.root.attributes("-topmost", True)

    if not filepath or not isinstance(filepath, str):
        _file_transcribing.release()
        return
    if not os.path.isfile(filepath):
        _file_transcribing.release()
        return
    if ui._app_closing[0]:
        _file_transcribing.release()
        return

    filename = os.path.basename(filepath)
    ui.set_statut_safe(ui.tr("file_transcribing", name=filename[:30]), COLOR_BLUE, COLOR_BLUE)
    try:
        threading.Thread(target=_transcribe_file_worker, args=(filepath, filename),
                         daemon=True).start()
    except Exception:
        _file_transcribing.release()


# ─────────────────────────────────────────────────────────────────────────
# Transcription worker (background thread)
# ─────────────────────────────────────────────────────────────────────────

def _transcribe_file_worker(filepath, filename):
    """Thread worker : transcrit un fichier audio et affiche les résultats."""
    try:
        model = _global_model[0]
        if model is None:
            ui.set_statut_safe(ui.tr("file_no_model"), COLOR_RED, COLOR_RED)
            return

        start_time = time.perf_counter()
        try:
            _lang = ui.config["language"]
            _common_kwargs = dict(
                language=_lang,
                initial_prompt=_file_initial_prompts.get(_lang, ""),
                condition_on_previous_text=True,
                no_speech_threshold=0.55,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                repetition_penalty=1.3,
            )

            # BatchedInferencePipeline (lazy import)
            if _HAS_BATCHED[0] is None:
                try:
                    from faster_whisper import BatchedInferencePipeline as _BIP
                    _HAS_BATCHED[0] = True
                    ui.log_error(msg="[FILE] BatchedInferencePipeline disponible")
                except ImportError:
                    _HAS_BATCHED[0] = False
                    ui.log_error(msg="[FILE] BatchedInferencePipeline non disponible")

            _used_batched = False
            if _HAS_BATCHED[0] and _detected_device == "cuda":
                try:
                    from faster_whisper import BatchedInferencePipeline as _BIP
                    _batched = _BIP(model=model)
                    ui.set_statut_safe(
                        ui.tr("file_progress", pct=0, elapsed=0) + " [GPU batch]",
                        COLOR_BLUE, COLOR_BLUE
                    )
                    segments_gen, info = _batched.transcribe(
                        filepath, batch_size=32, beam_size=1,
                        temperature=(0, 0.2, 0.4), **_common_kwargs,
                    )
                    _used_batched = True
                    ui.log_error(msg="[FILE] Mode BatchedInference (batch=32, beam=1, GPU)")
                except Exception as _be:
                    ui.log_error(_be, "BatchedInferencePipeline fallback")
                    _used_batched = False

            if not _used_batched:
                _seq_kwargs = dict(
                    beam_size=1, temperature=(0, 0.4, 0.8),
                    vad_filter=False, **_common_kwargs,
                )
                try:
                    segments_gen, info = model.transcribe(filepath, **_seq_kwargs)
                except TypeError:
                    for _k in ("repetition_penalty", "initial_prompt"):
                        _seq_kwargs.pop(_k, None)
                    segments_gen, info = model.transcribe(filepath, **_seq_kwargs)
                ui.log_error(msg=f"[FILE] Mode séquentiel (beam=1, {_detected_device})")

            audio_duration = getattr(info, 'duration', 0) or 0

            # Collecte des segments
            _segments_data = []
            _last_progress_time = time.perf_counter()
            _last_gc_time = time.perf_counter()
            _SEGMENT_TIMEOUT = 120

            gc.disable()
            try:
                for segment in segments_gen:
                    if ui._app_closing[0]:
                        return
                    if time.perf_counter() - _last_progress_time > _SEGMENT_TIMEOUT:
                        ui.log_error(msg=f"Transcription fichier timeout ({_SEGMENT_TIMEOUT}s)")
                        ui.set_statut_safe(ui.tr("file_timeout"), COLOR_ORANGE, COLOR_ORANGE)
                        break
                    _last_progress_time = time.perf_counter()
                    seg_text = segment.text.strip()
                    if seg_text:
                        _segments_data.append((seg_text, segment.start, segment.end))
                    if time.perf_counter() - _last_gc_time > 60:
                        gc.enable(); gc.collect(); gc.disable()
                        _last_gc_time = time.perf_counter()
                    if audio_duration > 0:
                        pct = min(99, int((segment.end / audio_duration) * 100))
                        elapsed = int(time.perf_counter() - start_time)
                        _mode = "batch" if _used_batched else "seq"
                        ui.set_statut_safe(
                            ui.tr("file_progress", pct=pct, elapsed=elapsed) + f" [{_mode}]",
                            COLOR_BLUE, COLOR_BLUE
                        )
            finally:
                gc.enable()

            result = _format_transcription(_segments_data)
            _last_file_segments[0] = list(_segments_data)
            _last_file_path[0] = filepath

        except Exception as e:
            ui.log_error(e, f"Transcription fichier échouée: {filepath}")
            err_msg = str(e).lower()
            if "decode" in err_msg or "audio" in err_msg or "av" in err_msg or "ffmpeg" in err_msg:
                ui.set_statut_safe(ui.tr("file_error_decode"), COLOR_RED, COLOR_RED)
            else:
                ui.set_statut_safe(ui.tr("file_error_generic", err=str(e)[:80]), COLOR_RED, COLOR_RED)
            return

        if ui._app_closing[0]:
            return
        total_time = int(time.perf_counter() - start_time)
        _speed = f"{audio_duration/total_time:.1f}x" if total_time > 0 and audio_duration > 0 else ""
        ui.set_statut_safe(
            ui.tr("file_done", duration=total_time) + (f" ({_speed} temps réel)" if _speed else ""),
            COLOR_GREEN, COLOR_GREEN
        )
        if not ui._app_closing[0]:
            final_text = result if result else ui.tr("file_empty")
            ui._safe_after(0, lambda: _show_file_result(filename, final_text))
    finally:
        _file_transcribing.release()


# ─────────────────────────────────────────────────────────────────────────
# File result window
# ─────────────────────────────────────────────────────────────────────────

def _show_file_result(filename, text):
    """Affiche le résultat de transcription dans une fenêtre Toplevel."""
    if ui._app_closing[0]:
        return
    if ui._file_transcribe_window[0] is not None:
        try:
            if ui._file_transcribe_window[0].winfo_exists():
                ui._file_transcribe_window[0].destroy()
        except Exception:
            pass

    t  = ui.theme()
    bg = t["bg"]
    fg = t["fg"]
    fg2 = t["fg2"]

    win = tk.Toplevel(ui.root)
    title_text = ui.tr("file_result_title", name=filename[:40])
    win.title(title_text + " - Whisper Helio")
    win.configure(bg=bg)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.95)
    win.overrideredirect(True)
    win.resizable(True, True)

    _copy_feedback_job = [None]

    def on_close_file():
        ui._file_transcribe_window[0] = None
        if _copy_feedback_job[0]:
            try: win.after_cancel(_copy_feedback_job[0])
            except Exception: pass
        try:
            if hasattr(win, '_rounded_job') and win._rounded_job:
                win.after_cancel(win._rounded_job)
            win.destroy()
        except tk.TclError:
            pass
    win.protocol("WM_DELETE_WINDOW", on_close_file)

    # ── Barre de titre ──
    _hdr_pad = max(8, int(14 * ui._SCALE))
    frame_hdr_f = tk.Frame(win, bg=bg)
    frame_hdr_f.pack(fill="x", padx=_hdr_pad, pady=(12, 0))

    _btn_cls_f = tk.Canvas(frame_hdr_f, width=32, height=32, bg=bg,
                           highlightthickness=0, cursor="hand2")
    _btn_cls_f.pack(side="right", padx=(8, 4))
    _cls_bg_f = _btn_cls_f.create_oval(2, 2, 30, 30, fill=COLOR_RED, outline="")
    _btn_cls_f.create_text(16, 16, text="\u2715", fill=COLOR_WHITE,
                           font=("Segoe UI", 11, "bold"))

    tk.Label(frame_hdr_f, text=title_text, bg=bg,
             fg=t.get("fg_title", fg), font=("Segoe UI", 13, "bold"),
             anchor="w").pack(side="left", fill="x", expand=True)

    _btn_cls_f.bind("<Enter>", lambda e: _btn_cls_f.itemconfig(_cls_bg_f, fill=COLOR_RED_DARK))
    _btn_cls_f.bind("<Leave>", lambda e: _btn_cls_f.itemconfig(_cls_bg_f, fill=COLOR_RED))
    _btn_cls_f.bind("<Button-1>", lambda e: on_close_file())

    _bind_toplevel_drag(frame_hdr_f, win)

    tk.Frame(win, height=1, bg=t.get("vu_color", "#22d3ee")).pack(
        fill="x", padx=_hdr_pad, pady=(8, 0))

    # ── Zone de texte ──
    text_frame = tk.Frame(win, bg=bg)
    text_widget = tk.Text(
        text_frame, wrap="word",
        bg=t.get("input_bg", "#2d2d44"), fg=t.get("input_fg", "white"),
        font=("Consolas", 11), insertbackground=t.get("input_fg", "white"),
        relief="flat", bd=8, selectbackground=COLOR_BLUE, selectforeground=COLOR_WHITE,
    )
    _ft_sb = tk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
    text_widget.configure(yscrollcommand=_ft_sb.set)
    _ft_sb.pack(side="right", fill="y")
    text_widget.pack(side="left", fill="both", expand=True)
    text_widget.insert("1.0", text)

    # ── Footer (packed BEFORE text_frame) ──
    footer = tk.Frame(win, bg=bg)
    footer.pack(fill="x", side="bottom", padx=12, pady=(4, 12))
    tk.Frame(footer, height=1, bg=fg2).pack(fill="x", pady=(0, 8))
    btn_frame = tk.Frame(footer, bg=bg)
    btn_frame.pack()

    # Copier tout
    _btn_copy = _create_pill_button(
        btn_frame, 150, PILL_H, ui.tr("file_copy_all").upper(),
        COLOR_BLUE, COLOR_BLUE_DARK, bg=bg, emoji="\U0001F4CB", tag="cp",
        pack_opts={"side": "left", "padx": (0, 10)},
    )

    def _do_copy(e=None):
        content = text_widget.get("1.0", "end-1c")
        if content:
            try:
                pyperclip.copy(content)
                _btn_copy.itemconfig("txt_cp", text=ui.tr("file_copied").upper())
                if _copy_feedback_job[0]:
                    try: win.after_cancel(_copy_feedback_job[0])
                    except Exception: pass
                _copy_feedback_job[0] = win.after(1500, lambda: _btn_copy.itemconfig(
                    "txt_cp", text=ui.tr("file_copy_all").upper()))
            except Exception as exc:
                ui.log_error(exc, "pyperclip.copy result")
    _btn_copy.bind("<Button-1>", _do_copy)

    # Exporter
    if _last_file_segments[0]:
        _create_pill_button(
            btn_frame, 150, PILL_H, ui.tr("export_btn"),
            COLOR_GREEN, COLOR_GREEN_HOVER, bg=bg, emoji="\U0001F4BE", tag="ex",
            callback=lambda e: _show_export_dialog(win),
            pack_opts={"side": "left", "padx": (0, 10)},
        )

    # Fermer
    _create_pill_button(
        btn_frame, 120, PILL_H, ui.tr("file_close").upper(),
        COLOR_RED, COLOR_RED_DARK, bg=bg, tag="cl",
        callback=lambda e: on_close_file(),
        pack_opts={"side": "left"},
    )

    text_frame.pack(fill="both", expand=True, padx=12, pady=(8, 4))
    win.bind("<Escape>", lambda e: on_close_file())
    text_widget.bind("<Control-a>", lambda e: (text_widget.tag_add("sel", "1.0", "end"), "break"))
    _finalize_toplevel(win, 600, 500)
    ui._file_transcribe_window[0] = win


# ─────────────────────────────────────────────────────────────────────────
# Export dialog
# ─────────────────────────────────────────────────────────────────────────

def _open_folder(path: str) -> None:
    """Ouvre un dossier dans l'Explorateur Windows."""
    try:
        os.startfile(os.path.realpath(path))
    except Exception:
        pass


def _show_export_dialog(parent_win):
    """Fenêtre de sélection des formats d'export."""
    segments = _last_file_segments[0]
    source   = _last_file_path[0]
    if not segments or not source:
        return

    t  = ui.theme()
    bg = t["bg"]
    fg = t["fg"]
    fg2 = t["fg2"]

    _src_dir  = os.path.dirname(source) or "."
    _src_name = os.path.splitext(os.path.basename(source))[0]
    _n_segs   = len(segments)
    _duration = max((end for _, _, end in segments), default=0.0)
    _dur_min  = int(_duration // 60)
    _dur_sec  = int(_duration % 60)

    dlg = tk.Toplevel(parent_win)
    dlg.title("Exporter — Whisper Hélio")
    dlg.configure(bg=bg)
    dlg.attributes("-topmost", True)
    dlg.attributes("-alpha", 0.95)
    dlg.overrideredirect(True)
    dlg.resizable(False, False)

    # En-tête
    hdr = tk.Frame(dlg, bg=bg)
    hdr.pack(fill="x", padx=16, pady=(14, 6))
    tk.Label(hdr, text=f"\U0001F4BE  {ui.tr('export_title')}",
             font=("Segoe UI", 13, "bold"), fg=fg, bg=bg).pack(anchor="w")
    _info_txt = f"{_n_segs} {ui.tr('export_segments')} \u00b7 {_dur_min}:{_dur_sec:02d}"
    tk.Label(hdr, text=_info_txt, font=("Segoe UI", 9), fg=fg2, bg=bg).pack(anchor="w")

    tk.Frame(dlg, height=1, bg=fg2).pack(fill="x", padx=16, pady=(6, 8))

    # Destination
    _dest_dir = [_src_dir]
    dest_frame = tk.Frame(dlg, bg=bg)
    dest_frame.pack(fill="x", padx=20, pady=(0, 8))
    tk.Label(dest_frame, text=ui.tr("export_folder"),
             font=("Segoe UI", 9), fg=fg2, bg=bg).pack(side="left")

    def _short(path):
        return path if len(path) <= 40 else "\u2026" + path[-37:]

    dest_lbl = tk.Label(dest_frame, text=_short(_dest_dir[0]),
                        font=("Consolas", 8), fg=COLOR_BLUE, bg=bg, cursor="hand2")
    dest_lbl.pack(side="left", padx=(4, 0))
    dest_lbl.bind("<Button-1>", lambda e: _open_folder(_dest_dir[0]))

    def _browse_dest():
        dlg.attributes("-topmost", False)
        try:
            chosen = filedialog.askdirectory(parent=dlg, initialdir=_dest_dir[0],
                                             title=ui.tr("export_browse"))
        finally:
            dlg.attributes("-topmost", True)
        if chosen:
            _dest_dir[0] = chosen
            dest_lbl.configure(text=_short(chosen))

    btn_browse = tk.Label(dest_frame, text="\U0001F4C2", font=("Segoe UI", 11),
                          fg=fg2, bg=bg, cursor="hand2", padx=4)
    btn_browse.pack(side="left", padx=(4, 0))
    btn_browse.bind("<Button-1>", lambda e: _browse_dest())

    # Formats
    checks_frame = tk.Frame(dlg, bg=bg)
    checks_frame.pack(fill="x", padx=20, pady=(0, 6))

    format_vars = {}
    _defaults = {"srt", "vtt", "txt_ts"}
    _format_desc = {
        "srt": "Import Premiere Pro, DaVinci, VLC\u2026",
        "vtt": "YouTube, navigateurs web",
        "txt_ts": "Relecture avec repères temporels",
        "txt": "Copier-coller simple",
        "json": "Traitement automatis\u00e9, API",
    }

    for key, fmt in EXPORT_FORMATS.items():
        row = tk.Frame(checks_frame, bg=bg)
        row.pack(fill="x", anchor="w")
        var = tk.BooleanVar(value=(key in _defaults))
        format_vars[key] = var
        tk.Checkbutton(
            row, text=fmt["label"], variable=var,
            font=("Segoe UI", 11), fg=fg, bg=bg,
            selectcolor=bg, activebackground=bg, activeforeground=fg,
            anchor="w", padx=4, pady=1,
        ).pack(side="left")
        desc = _format_desc.get(key, "")
        if desc:
            tk.Label(row, text=f"\u2014 {desc}",
                     font=("Segoe UI", 8), fg=fg2, bg=bg).pack(side="left", padx=(2, 0))

    # Status
    status_var = tk.StringVar(value="")
    status_lbl = tk.Label(dlg, textvariable=status_var, font=("Segoe UI", 9),
                          fg=COLOR_GREEN, bg=bg, wraplength=300, justify="left")
    status_lbl.pack(fill="x", padx=16, pady=(4, 4))

    # Boutons
    btn_bar = tk.Frame(dlg, bg=bg)
    btn_bar.pack(fill="x", padx=16, pady=(4, 14))

    _export_done = [False]

    def _do_export_action(e=None):
        if _export_done[0]:
            return
        selected = [k for k, v in format_vars.items() if v.get()]
        if not selected:
            status_var.set(f"\u26a0 {ui.tr('export_select_one')}")
            status_lbl.configure(fg=COLOR_RED)
            return
        _export_done[0] = True
        try:
            created = export_files(
                segments, source, selected,
                source_filename=os.path.basename(source),
                output_dir=_dest_dir[0],
            )
            if created:
                status_var.set("\u2705 " + ", ".join(created))
                status_lbl.configure(fg=COLOR_GREEN)
                ui.log_error(msg=f"[EXPORT] {len(created)} fichier(s) : {', '.join(created)}")
            else:
                status_var.set(f"\u26a0 {ui.tr('export_no_file')}")
                status_lbl.configure(fg=COLOR_RED)
                _export_done[0] = False
        except Exception as exc:
            ui.log_error(exc, "Export échoué")
            status_var.set(f"\u274c {str(exc)[:60]}")
            status_lbl.configure(fg=COLOR_RED)
            _export_done[0] = False

    _create_pill_button(
        btn_bar, 140, PILL_H, ui.tr("export_btn"),
        COLOR_GREEN, COLOR_GREEN_HOVER, bg=bg, tag="go",
        callback=_do_export_action,
        pack_opts={"side": "left", "padx": (0, 10)},
    )
    _create_pill_button(
        btn_bar, 110, PILL_H, ui.tr("export_close"),
        fg2, COLOR_GREY_HOVER, bg=bg, tag="cn",
        callback=lambda e: dlg.destroy(),
        pack_opts={"side": "left"},
    )
    dlg.bind("<Escape>", lambda e: dlg.destroy())
    _bind_toplevel_drag(hdr, dlg)
    _finalize_toplevel(dlg, 380, 400, min_w=340, min_h=320)


# ─────────────────────────────────────────────────────────────────────────
# Macros window
# ─────────────────────────────────────────────────────────────────────────

def _build_macros_tab(notebook, win, t):
    """Construit l'onglet Macros texte. Retourne macro_rows."""
    bg  = t["bg"]
    fg2 = t["fg2"]
    vc  = t.get("vu_color", "#22d3ee")
    _ibg = t.get("input_bg", "#2d2d44")
    _ifg = t.get("input_fg", "white")

    tab = tk.Frame(notebook, bg=bg)
    notebook.add(tab, text=f"  {ui.tr('macros_tab')}  ")

    _wrap_w = max(250, int(430 * ui._SCALE))
    tk.Label(tab, text=ui.tr("macro_help_text"), bg=bg, fg=COLOR_BLUE,
             font=("Consolas", 14), wraplength=_wrap_w).pack(pady=(8, 4))

    _mac_pad = max(8, int(16 * ui._SCALE))
    fh_m = tk.Frame(tab, bg=bg)
    fh_m.pack(fill="x", padx=_mac_pad)
    tk.Label(fh_m, text=ui.tr("macro_col_name"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left")
    tk.Label(fh_m, text=ui.tr("macro_col_text"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left", padx=(6, 0))

    _btn_add_m = _create_pill_button(
        tab, 150, PILL_H, ui.tr("macro_add"),
        vc, COLOR_RED, bg=bg, emoji="+", text_color=bg,
        font=PILL_FONT_LG, emoji_font=("Segoe UI", 13, "bold"),
        tag="btn_add_m", pack_opts={"pady": (6, 4)},
    )

    cs_m, if_m, _mw_m = _make_scroll_area(tab, bg)
    macro_rows = []
    _entry_w = max(8, int(13 * ui._SCALE))

    def add_macro_row(name="", text=""):
        row = tk.Frame(if_m, bg=bg)
        row.pack(fill="x", pady=2)
        vn = tk.StringVar(win, value=name)
        vt = tk.StringVar(win, value=text)
        en = tk.Entry(row, textvariable=vn, width=_entry_w,
                      bg=_ibg, fg=_ifg, font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        en.pack(side="left")
        et = tk.Entry(row, textvariable=vt,
                      bg=_ibg, fg=_ifg, font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        et.pack(side="left", fill="x", expand=True, padx=(6, 6))

        def del_m():
            try: macro_rows.remove((vn, vt))
            except ValueError: pass
            row.destroy()

        bd = tk.Button(row, text=ui.tr("macro_delete"), command=del_m,
                       bg=COLOR_RED_DARK, fg="white", relief="flat",
                       font=("Consolas", 14), cursor="hand2", padx=5)
        bd.pack(side="left")
        for w in (row, en, et, bd):
            w.bind("<MouseWheel>", _mw_m)
        macro_rows.append((vn, vt))

    for m in ui.config.get("macros", []):
        add_macro_row(m.get("name", ""), m.get("text", ""))

    def on_add_macro():
        add_macro_row()
        win.after(50, lambda: cs_m.yview_moveto(1.0))

    _btn_add_m.bind("<Button-1>", lambda e: on_add_macro())
    return macro_rows


def _build_actions_tab(notebook, win, t):
    """Construit l'onglet Actions vocales. Retourne (v_action_trigger, action_rows)."""
    bg  = t["bg"]
    fg  = t["fg"]
    fg2 = t["fg2"]
    vc  = t.get("vu_color", "#22d3ee")
    accent = t.get("btn_icon_bg", "#2a2a3e")
    _ibg = t.get("input_bg", "#2d2d44")
    _ifg = t.get("input_fg", "white")

    tab = tk.Frame(notebook, bg=bg)
    notebook.add(tab, text=f"  {ui.tr('actions_tab')}  ")

    _mac_pad = max(8, int(16 * ui._SCALE))
    _wrap_w  = max(250, int(430 * ui._SCALE))

    frame_trig = tk.Frame(tab, bg=bg)
    frame_trig.pack(fill="x", padx=_mac_pad, pady=(10, 2))
    tk.Label(frame_trig, text=ui.tr("action_trigger_label") + " :",
             bg=bg, fg=fg2, font=("Consolas", 16)).pack(side="left")
    v_action_trigger = tk.StringVar(win, value=ui.config.get("action_trigger", "action"))
    tk.Entry(frame_trig, textvariable=v_action_trigger, width=12,
             bg=_ibg, fg=_ifg, font=("Consolas", 16),
             insertbackground=_ifg, relief="flat", bd=4).pack(side="left", padx=6)

    tk.Label(tab, text=ui.tr("action_help"), bg=bg, fg=COLOR_BLUE,
             font=("Consolas", 14), wraplength=_wrap_w).pack(pady=(2, 6))

    # Actions intégrées
    tk.Label(tab, text=ui.tr("action_builtin"), bg=bg, fg=COLOR_PURPLE,
             font=("Consolas", 14, "bold")).pack(anchor="w", padx=_mac_pad)

    frame_builtin = tk.Frame(tab, bg=_ibg, bd=0)
    frame_builtin.pack(fill="x", padx=_mac_pad, pady=(4, 10))

    BUILTIN_DISPLAY = [
        "\U0001F5C2 explorateur", "\U0001F4BB bureau", "\U0001F4CA excel",
        "\U0001F4DD word", "\U0001F9EE calculatrice", "\U0001F4D3 bloc-notes",
        "\U0001F310 chrome", "\U0001F98A firefox", "\U0001F310 edge",
        "\u2699 taches", "\U0001F3A8 paint",
    ]
    trigger_example = ui.config.get("action_trigger", "action")
    for i, label in enumerate(BUILTIN_DISPLAY):
        col = i % 3
        row_i = i // 3
        cell = tk.Frame(frame_builtin, bg=accent, bd=1, relief="solid")
        cell.grid(row=row_i, column=col, padx=3, pady=3, sticky="ew")
        frame_builtin.grid_columnconfigure(col, weight=1)
        vocal_name = label.split(" ", 1)[1]
        tk.Label(cell, text=label, bg=accent, fg=fg,
                 font=("Consolas", 14, "bold")).pack(anchor="w", padx=6, pady=(4, 0))
        tk.Label(cell, text=ui.tr("action_say_hint", trigger=trigger_example, name=vocal_name),
                 bg=accent, fg=fg2, font=("Consolas", 12)).pack(anchor="w", padx=6, pady=(0, 4))

    # Actions personnalisées
    tk.Label(tab, text=ui.tr("action_custom"), bg=bg, fg=COLOR_GREEN,
             font=("Consolas", 14, "bold")).pack(anchor="w", padx=_mac_pad, pady=(6, 2))

    fh_a = tk.Frame(tab, bg=bg)
    fh_a.pack(fill="x", padx=_mac_pad, pady=(0, 2))
    tk.Label(fh_a, text=ui.tr("action_col_name"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left")
    tk.Label(fh_a, text=ui.tr("action_col_path"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left", padx=(6, 0))

    _btn_add_a = _create_pill_button(
        tab, 180, PILL_H, ui.tr("action_col_add"),
        vc, COLOR_GREEN, bg=bg, emoji="+", text_color=bg,
        font=PILL_FONT_LG, emoji_font=("Segoe UI", 13, "bold"),
        tag="btn_add_a", pad=1, pack_opts={"pady": (2, 4)},
    )

    # Zone scrollable actions perso
    _fa_scroll_outer = tk.Frame(tab, bg=bg)
    _fa_scroll_outer.pack(fill="x", expand=False, padx=_mac_pad, pady=0)
    cs_a = tk.Canvas(_fa_scroll_outer, bg=bg, highlightthickness=0, height=110)
    _fa_sb = tk.Scrollbar(_fa_scroll_outer, orient="vertical", command=cs_a.yview)
    cs_a.configure(yscrollcommand=_fa_sb.set)
    if_a = tk.Frame(cs_a, bg=bg)
    _fa_win = cs_a.create_window((0, 0), window=if_a, anchor="nw")

    _fa_sb_visible = [False]
    def _fa_on_inner_configure(e):
        cs_a.configure(scrollregion=cs_a.bbox("all"))
        need_sb = if_a.winfo_reqheight() > cs_a.winfo_height()
        if need_sb and not _fa_sb_visible[0]:
            _fa_sb.pack(side="right", fill="y")
            _fa_sb_visible[0] = True
        elif not need_sb and _fa_sb_visible[0]:
            _fa_sb.pack_forget()
            _fa_sb_visible[0] = False
    def _fa_on_canvas_configure(e):
        cs_a.itemconfig(_fa_win, width=e.width)
    if_a.bind("<Configure>", _fa_on_inner_configure)
    cs_a.bind("<Configure>", _fa_on_canvas_configure)
    cs_a.pack(side="left", fill="both", expand=True)

    _mw_a_accum = [0.0]
    def _mw_a(e):
        _mw_a_accum[0] += -e.delta / 120.0
        lines = int(_mw_a_accum[0])
        if lines:
            cs_a.yview_scroll(lines, "units")
            _mw_a_accum[0] -= lines

    action_rows = []
    _entry_w = max(8, int(13 * ui._SCALE))

    def add_action_row(name="", path=""):
        row = tk.Frame(if_a, bg=bg)
        row.pack(fill="x", pady=2)
        vn = tk.StringVar(win, value=name)
        vp = tk.StringVar(win, value=path)
        en = tk.Entry(row, textvariable=vn, width=_entry_w,
                      bg=_ibg, fg=_ifg, font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        en.pack(side="left")
        ep = tk.Entry(row, textvariable=vp,
                      bg=_ibg, fg=_ifg, font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        ep.pack(side="left", fill="x", expand=True, padx=(6, 4))

        def browse():
            win.attributes("-topmost", False)
            try:
                f = filedialog.askopenfilename(
                    parent=win, title=ui.tr("action_browse_title"),
                    filetypes=[(ui.tr("action_browse_filter"), "*.exe"),
                               (ui.tr("file_all_types"), "*.*")])
            finally:
                win.attributes("-topmost", True)
            if f and isinstance(f, str):
                vp.set(f)

        tk.Button(row, text=ui.tr("action_browse"), command=browse,
                  bg=COLOR_BLUE_DARK, fg="white", relief="flat",
                  font=("Consolas", 14), cursor="hand2", padx=5).pack(side="left")

        def del_a():
            try: action_rows.remove((vn, vp))
            except ValueError: pass
            row.destroy()

        tk.Button(row, text=ui.tr("action_delete"), command=del_a,
                  bg=COLOR_RED_DARK, fg="white", relief="flat",
                  font=("Consolas", 14), cursor="hand2", padx=5).pack(side="left", padx=(2, 0))
        for w in (row, en, ep):
            w.bind("<MouseWheel>", _mw_a)
        action_rows.append((vn, vp))

    for a in ui.config.get("actions", []):
        add_action_row(a.get("name", ""), a.get("path", ""))

    def on_add_action():
        add_action_row()
        win.after(50, lambda: cs_a.yview_moveto(1.0))
    _btn_add_a.bind("<Button-1>", lambda e: on_add_action())
    return v_action_trigger, action_rows


def _build_dict_tab(notebook, win, t):
    """Construit l'onglet Dictionnaire. Retourne dict_rows."""
    bg  = t["bg"]
    fg2 = t["fg2"]
    vc  = t.get("vu_color", "#22d3ee")
    accent = t.get("btn_icon_bg", "#2a2a3e")
    _ibg = t.get("input_bg", "#2d2d44")
    _ifg = t.get("input_fg", "white")

    tab = tk.Frame(notebook, bg=bg)
    notebook.add(tab, text=f"  {ui.tr('dict_tab')}  ")

    _mac_pad = max(8, int(16 * ui._SCALE))
    _wrap_w  = max(250, int(430 * ui._SCALE))

    tk.Label(tab, text=ui.tr("dict_help"), bg=bg, fg=COLOR_BLUE,
             font=("Consolas", 14), wraplength=_wrap_w).pack(pady=(10, 2))
    tk.Label(tab, text=ui.tr("dict_example"), bg=bg, fg=fg2,
             font=("Consolas", 14), wraplength=_wrap_w).pack(pady=(0, 6))

    fh_d = tk.Frame(tab, bg=bg)
    fh_d.pack(fill="x", padx=_mac_pad)
    tk.Label(fh_d, text=ui.tr("dict_wrong"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left")
    tk.Label(fh_d, text="\u2192", bg=bg, fg=COLOR_ORANGE,
             font=("Consolas", 16, "bold")).pack(side="left", padx=(4, 4))
    tk.Label(fh_d, text=ui.tr("dict_correct"), bg=bg, fg=fg2,
             font=("Consolas", 14, "bold"), anchor="w").pack(side="left")

    _btn_add_d = _create_pill_button(
        tab, 180, PILL_H, ui.tr("dict_col_add"),
        vc, COLOR_RED, bg=bg, emoji="+", text_color=bg,
        font=PILL_FONT_LG, emoji_font=("Segoe UI", 13, "bold"),
        tag="btn_add_d", pad=1, pack_opts={"pady": (6, 4)},
    )

    cs_d, if_d, _mw_d = _make_scroll_area(tab, bg)
    dict_rows = []

    def add_dict_row(wrong="", correct=""):
        _row_even_bg = _ibg
        _row_odd_bg  = accent
        row_bg = _row_even_bg if len(dict_rows) % 2 == 0 else _row_odd_bg
        row = tk.Frame(if_d, bg=row_bg)
        row.pack(fill="x", pady=1)
        vw = tk.StringVar(win, value=wrong)
        v_cor = tk.StringVar(win, value=correct)

        _dict_w = max(10, int(20 * ui._SCALE))
        ew = tk.Entry(row, textvariable=vw, width=_dict_w,
                      bg=_ibg, fg="#ff9966", font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        ew.pack(side="left", padx=(6, 0), pady=4)
        tk.Label(row, text="\u2192", bg=row_bg, fg=COLOR_ORANGE,
                 font=("Consolas", 10, "bold")).pack(side="left", padx=(4, 4))

        def del_d():
            try: dict_rows.remove((vw, v_cor))
            except ValueError: pass
            row.destroy()

        bd = tk.Button(row, text=ui.tr("dict_delete"), command=del_d,
                       bg=COLOR_RED_DARK, fg="white", relief="flat",
                       font=("Consolas", 14), cursor="hand2", padx=5)
        bd.pack(side="right", padx=(0, 6), pady=4)
        ec = tk.Entry(row, textvariable=v_cor,
                      bg=_ibg, fg=COLOR_GREEN, font=("Consolas", 16),
                      insertbackground=_ifg, relief="flat", bd=4)
        ec.pack(side="left", fill="x", expand=True, padx=(0, 4), pady=4)
        for w in (row, ew, ec, bd):
            w.bind("<MouseWheel>", _mw_d)
        dict_rows.append((vw, v_cor))

    for d in ui.config.get("dictionary", []):
        add_dict_row(d.get("wrong", ""), d.get("correct", ""))

    def on_add_dict():
        add_dict_row()
        win.after(50, lambda: cs_d.yview_moveto(1.0))
    _btn_add_d.bind("<Button-1>", lambda e: on_add_dict())
    return dict_rows


def open_macros():
    """Ouvre le gestionnaire de macros et actions vocales (3 onglets)."""
    if ui._macros_window[0] is not None:
        try:
            if ui._macros_window[0].winfo_exists():
                ui._macros_window[0].lift()
                ui._macros_window[0].focus_force()
                return
        except Exception:
            pass

    t   = ui.theme()
    bg  = t["bg"]
    fg  = t["fg"]
    fg2 = t["fg2"]
    vc  = t.get("vu_color", "#22d3ee")
    accent = t.get("btn_icon_bg", "#2a2a3e")

    win = tk.Toplevel(ui.root)
    ui._macros_window[0] = win
    win.title(ui.tr("macro_title") + " - Whisper Hélio")
    win.configure(bg=bg)
    win.attributes("-topmost", True)
    win.resizable(True, True)
    win.overrideredirect(True)

    def on_close_macros():
        ui._macros_window[0] = None
        try:
            if hasattr(win, '_rounded_job') and win._rounded_job:
                win.after_cancel(win._rounded_job)
            win.destroy()
        except tk.TclError:
            pass
    win.protocol("WM_DELETE_WINDOW", on_close_macros)

    # Header
    _mac_hdr_pad = max(8, int(14 * ui._SCALE))
    frame_hdr = tk.Frame(win, bg=bg)
    frame_hdr.pack(fill="x", padx=_mac_hdr_pad, pady=(12, 0))
    tk.Label(frame_hdr, text=ui.tr("macro_title"), bg=bg,
             fg=t.get("fg_title", fg), font=("Segoe UI", 16, "bold")).pack(side="left", expand=True)

    btn_cls = tk.Canvas(frame_hdr, width=22, height=22, bg=bg, highlightthickness=0, cursor="hand2")
    btn_cls.pack(side="right")
    _bc_bg  = btn_cls.create_oval(1, 1, 21, 21, fill=accent, outline="")
    _bc_txt = btn_cls.create_text(11, 11, text="\u2715", fill=fg2, font=("Segoe UI", 8, "bold"))
    def _bc_enter(e): btn_cls.itemconfig(_bc_bg, fill=COLOR_RED_DARK); btn_cls.itemconfig(_bc_txt, fill="white")
    def _bc_leave(e): btn_cls.itemconfig(_bc_bg, fill=accent); btn_cls.itemconfig(_bc_txt, fill=fg2)
    btn_cls.bind("<Button-1>", lambda e: on_close_macros())
    btn_cls.bind("<Enter>", _bc_enter)
    btn_cls.bind("<Leave>", _bc_leave)

    _bind_toplevel_drag(frame_hdr, win)

    tk.Frame(win, height=1, bg=vc).pack(fill="x", padx=_mac_hdr_pad, pady=(8, 0))

    # Notebook style
    _nb_style = ttk.Style(win)
    _nb_style.theme_use("default")
    _nb_style.configure("Helio.TNotebook", background=bg, borderwidth=0)
    _nb_style.configure("Helio.TNotebook.Tab",
                        background=accent, foreground=fg2,
                        font=("Segoe UI", 14, "bold"), padding=[14, 7])
    _nb_style.map("Helio.TNotebook.Tab",
                   background=[("selected", vc)],
                   foreground=[("selected", bg)])

    # Footer (packed BEFORE notebook)
    footer_frame = tk.Frame(win, bg=bg)
    footer_frame.pack(side="bottom", fill="x", padx=_mac_hdr_pad, pady=(4, 14))
    tk.Frame(footer_frame, height=1, bg=fg2).pack(fill="x", pady=(0, 8))
    _btn_save = _create_pill_button(
        footer_frame, 200, PILL_H_LG, ui.tr("save_button"),
        COLOR_SAVE, COLOR_SAVE_HOVER, bg=bg,
        emoji="\U0001F4BE", font=PILL_FONT_LG, tag="bs",
    )

    notebook = ttk.Notebook(win, style="Helio.TNotebook")
    notebook.pack(fill="both", expand=True, padx=max(6, int(12 * ui._SCALE)), pady=(8, 0))

    macro_rows = _build_macros_tab(notebook, win, t)
    v_action_trigger, action_rows = _build_actions_tab(notebook, win, t)
    dict_rows = _build_dict_tab(notebook, win, t)

    def save_all():
        _MAX_NAME = 200
        _MAX_TEXT = 10000
        _MAX_ENTRIES = 500
        ui.config["macros"] = [
            {"name": vn.get().strip()[:_MAX_NAME], "text": vt.get()[:_MAX_TEXT]}
            for vn, vt in macro_rows if vn.get().strip()
        ]
        ui.config["action_trigger"] = (v_action_trigger.get().strip().replace(" ", "")[:_MAX_NAME]) or "action"
        ui.config["actions"] = [
            {"name": vn.get().strip().replace(" ", "_")[:_MAX_NAME], "path": vp.get().strip()}
            for vn, vp in action_rows if vn.get().strip() and vp.get().strip()
        ]
        ui.config["dictionary"] = [
            {"wrong": vw.get().strip()[:_MAX_NAME], "correct": v_cor.get()[:_MAX_TEXT]}
            for vw, v_cor in dict_rows if vw.get().strip()
        ]
        for _key in ("macros", "actions", "dictionary"):
            if len(ui.config.get(_key, [])) > _MAX_ENTRIES:
                ui.config[_key] = ui.config[_key][:_MAX_ENTRIES]
        ui.save_config(ui.config)
        on_close_macros()

    _btn_save.bind("<Button-1>", lambda e: save_all())
    _finalize_toplevel(win, 700, 820, min_h=400)
