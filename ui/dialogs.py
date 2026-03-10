"""
Dialog windows — Help (README) and Settings.

All shared references are accessed via ``ui.*`` (late binding).
"""
from __future__ import annotations

import os
import re
import sys
import tkinter as tk

import ui
from ui import (
    COLOR_BLUE, COLOR_BLUE_DARK, COLOR_RED, COLOR_RED_DARK,
    COLOR_WHITE, COLOR_PURPLE, COLOR_SAVE, COLOR_SAVE_HOVER,
    PILL_H, PILL_H_LG, PILL_FONT_LG,
)
from ui.helpers import (
    _create_pill_button, _finalize_toplevel, _bind_toplevel_drag,
)
from core.config import (
    VALID_MODELS, VALID_HOTKEYS, VALID_THEMES,
    VALID_DEVICES, VALID_LANGUAGES, VALID_POSITIONS, VALID_UI_LANGS,
    BASE_DIR,
)

# ── Regex pré-compilés pour le parsing Markdown ──────────────────────────
_RE_MD_LINK   = re.compile(r'\[([^\]]+)\]\([^)]+\)')
_RE_MD_BOLD   = re.compile(r'\*\*([^*]+)\*\*')
_RE_MD_ITALIC = re.compile(r'\*([^*]+)\*')


# ─────────────────────────────────────────────────────────────────────────
# Help window (README.md)
# ─────────────────────────────────────────────────────────────────────────

def open_help():
    """Ouvre une fenêtre affichant le README.md."""
    if ui._app_closing[0]:
        return
    if ui._help_window[0] is not None:
        try:
            if ui._help_window[0].winfo_exists():
                ui._help_window[0].lift()
                return
        except Exception:
            pass

    _base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv[0] else __file__)))
    _readme_path = os.path.join(_base, "README.md")
    if not os.path.isfile(_readme_path):
        _readme_path = os.path.join(os.path.dirname(_base), "README.md")
    if not os.path.isfile(_readme_path):
        # Fallback: à côté de BASE_DIR (core/config)
        _readme_path = os.path.join(str(BASE_DIR), "README.md")
    if not os.path.isfile(_readme_path):
        ui.set_statut_safe(ui.tr("help_not_found"), COLOR_RED, COLOR_RED)
        return

    try:
        with open(_readme_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        ui.set_statut_safe(ui.tr("help_not_found"), COLOR_RED, COLOR_RED)
        return

    t  = ui.theme()
    bg = t["bg"]
    fg = t["fg"]
    fg2 = t["fg2"]

    win = tk.Toplevel(ui.root)
    win.title(ui.tr("help_title"))
    win.configure(bg=bg)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.95)
    win.overrideredirect(True)
    win.resizable(True, True)

    def on_close_help():
        ui._help_window[0] = None
        try:
            if hasattr(win, '_rounded_job') and win._rounded_job:
                win.after_cancel(win._rounded_job)
            win.destroy()
        except tk.TclError:
            pass
    win.protocol("WM_DELETE_WINDOW", on_close_help)

    # ── Barre de titre custom ──
    _hdr_pad = max(8, int(14 * ui._SCALE))
    frame_hdr = tk.Frame(win, bg=bg)
    frame_hdr.pack(fill="x", padx=_hdr_pad, pady=(12, 0))

    _btn_cls = tk.Canvas(frame_hdr, width=32, height=32, bg=bg,
                         highlightthickness=0, cursor="hand2")
    _btn_cls.pack(side="right", padx=(8, 4))
    _cls_bg  = _btn_cls.create_oval(2, 2, 30, 30, fill=COLOR_RED, outline="")
    _btn_cls.create_text(16, 16, text="\u2715", fill=COLOR_WHITE,
                         font=("Segoe UI", 11, "bold"))
    _btn_cls.bind("<Enter>", lambda e: _btn_cls.itemconfig(_cls_bg, fill=COLOR_RED_DARK))
    _btn_cls.bind("<Leave>", lambda e: _btn_cls.itemconfig(_cls_bg, fill=COLOR_RED))
    _btn_cls.bind("<Button-1>", lambda e: on_close_help())

    tk.Label(frame_hdr, text=ui.tr("help_title"), bg=bg,
             fg=t.get("fg_title", fg), font=("Segoe UI", 13, "bold"),
             anchor="w").pack(side="left", fill="x", expand=True)

    _bind_toplevel_drag(frame_hdr, win)

    tk.Frame(win, height=1, bg=t.get("vu_color", "#22d3ee")).pack(
        fill="x", padx=_hdr_pad, pady=(8, 0))

    # ── Zone de texte scrollable ──
    text_frame = tk.Frame(win, bg=bg)
    text_frame.pack(fill="both", expand=True, padx=12, pady=(8, 4))

    text_widget = tk.Text(
        text_frame, wrap="word",
        bg=t.get("input_bg", "#2d2d44"),
        fg=t.get("input_fg", "white"),
        font=("Consolas", 11),
        insertbackground=t.get("input_fg", "white"),
        relief="flat", bd=8,
        selectbackground=COLOR_BLUE,
        selectforeground=COLOR_WHITE,
        state="normal",
    )
    sb = tk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
    text_widget.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    text_widget.pack(side="left", fill="both", expand=True)

    # Tags
    text_widget.tag_configure("h1", font=("Segoe UI", 15, "bold"),
                              foreground=t.get("fg_title", COLOR_WHITE))
    text_widget.tag_configure("h2", font=("Segoe UI", 13, "bold"),
                              foreground=COLOR_BLUE)
    text_widget.tag_configure("h3", font=("Segoe UI", 11, "bold"),
                              foreground=COLOR_PURPLE)
    text_widget.tag_configure("bold", font=("Consolas", 11, "bold"))
    text_widget.tag_configure("sep", foreground=fg2)

    # ── Filtrage du README ──
    lines = content.splitlines()
    _start = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("## ") or (s.startswith("---") and i > 0):
            _start = i
            break

    text_widget.insert("end", "Whisper Hélio v1.5\n", "h1")
    text_widget.insert("end", "Dictée vocale Windows — 100% offline\n\n")

    _skip_prefixes = ("[![", "<p", "</p>", "<a", "</a>", "<img",
                       "<strong>", "</strong>", "![")

    for line in lines[_start:]:
        stripped = line.strip()
        if stripped.startswith(_skip_prefixes):
            continue
        if stripped.startswith("### "):
            text_widget.insert("end", stripped[4:] + "\n", "h3")
        elif stripped.startswith("## "):
            text_widget.insert("end", "\n" + stripped[3:] + "\n", "h2")
        elif stripped.startswith("# "):
            text_widget.insert("end", stripped[2:] + "\n", "h1")
        elif stripped.startswith("---") or stripped.startswith("==="):
            text_widget.insert("end", "\u2500" * 50 + "\n", "sep")
        elif stripped == "":
            text_widget.insert("end", "\n")
        else:
            clean = _RE_MD_LINK.sub(r'\1', stripped)
            clean = _RE_MD_BOLD.sub(r'\1', clean)
            clean = _RE_MD_ITALIC.sub(r'\1', clean)
            text_widget.insert("end", clean + "\n")

    text_widget.configure(state="disabled")

    # ── Footer ──
    footer = tk.Frame(win, bg=bg)
    footer.pack(fill="x", padx=12, pady=(4, 12))
    tk.Frame(footer, height=1, bg=fg2).pack(fill="x", pady=(0, 8))

    _create_pill_button(
        footer, 120, PILL_H, ui.tr("file_close").upper(),
        COLOR_RED, COLOR_RED_DARK, bg=bg, tag="hc",
        callback=lambda e: on_close_help(),
    )

    _finalize_toplevel(win, 600, 700)
    ui._help_window[0] = win


# ─────────────────────────────────────────────────────────────────────────
# Settings window
# ─────────────────────────────────────────────────────────────────────────

def open_settings(*, hw_info, streamer, on_save):
    """Ouvre la fenêtre des paramètres.

    Parameters
    ----------
    hw_info : str
        Texte d'information matériel affiché dans la fenêtre.
    streamer : StreamingTranscriber
        Instance du streaming temps réel.
    on_save : callable(new_settings: dict, streaming: bool)
        Callback appelé quand l'utilisateur clique "Sauvegarder".
        Reçoit un dict des settings et l'état streaming.
    """
    if ui._settings_window[0] is not None:
        try:
            if ui._settings_window[0].winfo_exists():
                ui._settings_window[0].lift()
                ui._settings_window[0].focus_force()
                return
        except Exception:
            pass

    t = ui.theme()
    win = tk.Toplevel(ui.root)
    ui._settings_window[0] = win
    win.title(ui.tr("settings") + " - Whisper Hélio")
    win.configure(bg=t["bg"])
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.93)
    win.overrideredirect(True)
    win.resizable(True, True)

    def on_close_settings():
        ui._settings_window[0] = None
        try:
            if hasattr(win, '_rounded_job') and win._rounded_job:
                win.after_cancel(win._rounded_job)
            win.destroy()
        except tk.TclError:
            pass
    win.protocol("WM_DELETE_WINDOW", on_close_settings)

    # ── Barre de titre custom ──
    _title_bar = tk.Frame(win, bg=t.get("header_bg", t["bg"]), height=32)
    _title_bar.pack(fill="x", padx=0, pady=0)
    _title_bar.pack_propagate(False)
    tk.Label(_title_bar, text=ui.tr("settings") + " — Whisper Hélio",
             bg=t.get("header_bg", t["bg"]), fg=t["fg"],
             font=("Consolas", 16, "bold")).pack(side="left", padx=12)

    _btn_cls = tk.Canvas(_title_bar, width=22, height=22,
                         bg=t.get("header_bg", t["bg"]), highlightthickness=0, cursor="hand2")
    _btn_cls.pack(side="right", padx=(0, 6), pady=5)
    _cls_bg  = _btn_cls.create_oval(1, 1, 21, 21, fill=t.get("btn_icon_bg", "#2a2a3e"), outline="")
    _cls_txt = _btn_cls.create_text(11, 11, text="\u2715", fill=t["btn_fg"], font=("Segoe UI", 8, "bold"))
    def _cls_enter(e): _btn_cls.itemconfig(_cls_bg, fill=COLOR_RED_DARK); _btn_cls.itemconfig(_cls_txt, fill=COLOR_WHITE)
    def _cls_leave(e): _btn_cls.itemconfig(_cls_bg, fill=t.get("btn_icon_bg", "#2a2a3e")); _btn_cls.itemconfig(_cls_txt, fill=t["btn_fg"])
    _btn_cls.bind("<Enter>",    _cls_enter)
    _btn_cls.bind("<Leave>",    _cls_leave)
    _btn_cls.bind("<Button-1>", lambda e: on_close_settings())

    _bind_toplevel_drag(_title_bar, win)

    tk.Frame(win, bg=t.get("sep", "#3a3a52"), height=1).pack(fill="x")

    # ── Zone scrollable ──
    _set_canvas = tk.Canvas(win, bg=t["bg"], highlightthickness=0)
    _set_scrollbar = tk.Scrollbar(win, orient="vertical", command=_set_canvas.yview)
    _set_inner = tk.Frame(_set_canvas, bg=t["bg"])

    _set_wid = _set_canvas.create_window((0, 0), window=_set_inner, anchor="nw")
    _set_canvas.configure(yscrollcommand=_set_scrollbar.set)
    def _set_resize_inner(e):
        _set_canvas.itemconfig(_set_wid, width=e.width)
    _set_canvas.bind("<Configure>", _set_resize_inner)

    _set_canvas.pack(side="left", fill="both", expand=True)
    _set_sb_visible = [False]
    def _set_check_scrollbar(e=None):
        _set_canvas.configure(scrollregion=_set_canvas.bbox("all"))
        need = _set_inner.winfo_reqheight() > _set_canvas.winfo_height()
        if need and not _set_sb_visible[0]:
            _set_scrollbar.pack(side="right", fill="y")
            _set_sb_visible[0] = True
        elif not need and _set_sb_visible[0]:
            _set_scrollbar.pack_forget()
            _set_sb_visible[0] = False
    _set_inner.bind("<Configure>", _set_check_scrollbar)

    _set_scroll_accum = [0.0]
    def _set_mousewheel(e):
        _set_scroll_accum[0] += -e.delta / 120.0
        lines = int(_set_scroll_accum[0])
        if lines:
            _set_canvas.yview_scroll(lines, "units")
            _set_scroll_accum[0] -= lines
    def _bind_mw_recursive(widget):
        widget.bind("<MouseWheel>", _set_mousewheel)
        for child in widget.winfo_children():
            _bind_mw_recursive(child)
    win.after(100, lambda: _bind_mw_recursive(win))

    # ── Contenu ──
    tk.Label(_set_inner, text=ui.tr("hardware", hw=hw_info), bg=t["bg"], fg=COLOR_PURPLE,
             font=("Consolas", 14)).pack(pady=(14, 10))

    _pad_x = max(10, int(30 * ui._SCALE))
    frame = tk.Frame(_set_inner, bg=t["bg"])
    frame.pack(fill="x", padx=_pad_x, pady=5)

    v_theme = tk.StringVar(win, value=ui.config["theme"])
    v_model = tk.StringVar(win, value=ui.config["model"])
    v_device = tk.StringVar(win, value=ui.config["device"])
    v_lang = tk.StringVar(win, value=ui.config["language"])
    v_hotkey = tk.StringVar(win, value=ui.config["hotkey"])
    v_position = tk.StringVar(win, value=ui.config["position"])
    v_ui_lang = tk.StringVar(win, value=ui.config["ui_lang"])

    labels = [
        (ui.tr("theme"), v_theme, VALID_THEMES),
        (ui.tr("model"), v_model, VALID_MODELS),
        (ui.tr("device"), v_device, VALID_DEVICES),
        (ui.tr("lang"), v_lang, VALID_LANGUAGES),
        (ui.tr("shortcut"), v_hotkey, VALID_HOTKEYS),
        (ui.tr("position"), v_position, VALID_POSITIONS),
        (ui.tr("ui_lang"), v_ui_lang, VALID_UI_LANGS),
    ]

    _lbl_w = max(10, int(18 * ui._SCALE))
    for label_text, var, options in labels:
        f = tk.Frame(frame, bg=t["bg"])
        f.pack(fill="x", pady=6)
        tk.Label(f, text=label_text, bg=t["bg"], fg=t["fg2"],
                 font=("Consolas", 16), width=_lbl_w, anchor="w").pack(side="left")
        menu = tk.OptionMenu(f, var, *options)
        _ibg = t.get("input_bg", "#2d2d44")
        _ifg = t.get("input_fg", "white")
        _ihv = t.get("input_hover", "#3d3d54")
        menu.config(bg=_ibg, fg=_ifg, font=("Consolas", 16),
                   activebackground=_ihv, activeforeground=_ifg,
                   highlightthickness=0)
        menu["menu"].config(bg=_ibg, fg=_ifg, font=("Consolas", 16))
        menu.pack(side="left", fill="x", expand=True, padx=(8, 0))

    # ── Streaming ──
    v_streaming = tk.BooleanVar(win, value=ui.config.get("streaming", True))
    _sf_stream = tk.Frame(frame, bg=t["bg"])
    _sf_stream.pack(fill="x", pady=6)
    tk.Label(_sf_stream, text=ui.tr("streaming_label"), bg=t["bg"], fg=t["fg2"],
             font=("Consolas", 16), width=_lbl_w, anchor="w").pack(side="left")
    tk.Checkbutton(
        _sf_stream, variable=v_streaming,
        bg=t["bg"], fg=t["fg2"], selectcolor=t.get("input_bg", "#2d2d44"),
        activebackground=t["bg"], activeforeground=t["fg2"],
        font=("Consolas", 14), text=ui.tr("streaming_desc"),
    ).pack(side="left", padx=(8, 0))

    tk.Label(_set_inner, text=ui.tr("restart_note"), bg=t["bg"], fg=COLOR_RED,
             font=("Consolas", 14)).pack(pady=(15, 8))

    _settings_vars = {
        "theme": v_theme, "model": v_model, "device": v_device,
        "language": v_lang, "hotkey": v_hotkey, "position": v_position,
        "ui_lang": v_ui_lang,
    }

    def save_and_close():
        new_settings = {key: var.get() for key, var in _settings_vars.items()}
        streaming_enabled = v_streaming.get()
        on_save(new_settings, streaming_enabled)
        on_close_settings()

    # ── Bouton Sauvegarder ──
    _sf = tk.Frame(_set_inner, bg=t["bg"])
    _sf.pack(pady=(8, 20))
    _create_pill_button(
        _sf, 200, PILL_H_LG, ui.tr("save_button"),
        COLOR_SAVE, COLOR_SAVE_HOVER, bg=t["bg"],
        emoji="\U0001F4BE", font=PILL_FONT_LG, tag="sv",
        callback=lambda e: save_and_close(),
    )

    _finalize_toplevel(win, 620, 720, min_h=400)
