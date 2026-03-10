"""
UI helper functions — pill buttons, toplevel utilities, scroll areas.

All shared references (root, theme, _SCALE, etc.) are accessed via the
``ui`` package context, set by dictee.pyw at startup.
"""
from __future__ import annotations

import tkinter as tk
import ctypes
import ctypes.wintypes

import ui  # late-binding access to shared context


# ─────────────────────────────────────────────────────────────────────────
# Pill drawing
# ─────────────────────────────────────────────────────────────────────────

def _draw_pill(canvas, w, h, color, tag, pad=2):
    """Dessine un rectangle arrondi (pill) sur un Canvas via tag."""
    r = h // 2
    canvas.create_oval(pad, pad, h - pad, h - pad, fill=color, outline="", tags=tag)
    canvas.create_oval(w - h + pad, pad, w - pad, h - pad, fill=color, outline="", tags=tag)
    canvas.create_rectangle(r, pad, w - r, h - pad, fill=color, outline="", tags=tag)


def _create_pill_button(
    parent, width, height, text, color, color_hover,
    bg=None, emoji=None, text_color="white",
    font=None, emoji_font=None,
    tag="pill", pad=2, callback=None, pack_opts=None,
):
    """
    Factory pour bouton pill Canvas avec hover automatique.

    Parameters
    ----------
    parent : tk widget parent
    width, height : dimensions du bouton
    text : texte affiché
    color / color_hover : couleurs normal / survol
    bg : couleur de fond du Canvas (défaut: thème courant)
    emoji : emoji/icône affiché dans la partie gauche (optionnel)
    text_color : couleur du texte et de l'emoji
    font : police du texte
    emoji_font : police de l'emoji
    tag : préfixe pour les tags Canvas (bg_{tag}, txt_{tag})
    pad : marge interne du pill
    callback : fonction appelée au clic (optionnel)
    pack_opts : dict d'options pour pack() (optionnel)

    Returns
    -------
    tk.Canvas : le bouton (avec tags bg_{tag} et txt_{tag})
    """
    # Lazy imports for default fonts (set in dictee.pyw constants)
    if font is None:
        font = ("Segoe UI", 11, "bold")
    if emoji_font is None:
        emoji_font = ("Segoe UI", 12)
    if bg is None:
        bg = ui.theme()["bg"]
    btn = tk.Canvas(parent, width=width, height=height, bg=bg,
                    highlightthickness=0, cursor="hand2")
    if pack_opts:
        btn.pack(**pack_opts)
    else:
        btn.pack()

    bg_tag  = f"bg_{tag}"
    txt_tag = f"txt_{tag}"

    _draw_pill(btn, width, height, color, bg_tag, pad=pad)

    if emoji:
        # Emoji dans l'arrondi gauche, texte dans l'espace droit
        btn.create_text(height // 2, height // 2, text=emoji,
                        font=emoji_font, fill=text_color)
        btn.create_text(height + (width - height) // 2, height // 2,
                        text=text, fill=text_color, font=font, tags=txt_tag)
    else:
        # Texte centré
        btn.create_text(width // 2, height // 2,
                        text=text, fill=text_color, font=font, tags=txt_tag)

    # Hover automatique
    btn.bind("<Enter>", lambda e: btn.itemconfig(bg_tag, fill=color_hover))
    btn.bind("<Leave>", lambda e: btn.itemconfig(bg_tag, fill=color))

    if callback:
        btn.bind("<Button-1>", callback)

    return btn


# ─────────────────────────────────────────────────────────────────────────
# Toplevel utilities
# ─────────────────────────────────────────────────────────────────────────

def _finalize_toplevel(win, desired_w, desired_h, min_w=380, min_h=300):
    """Dimensionne, centre et applique coins arrondis à un Toplevel."""
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    ww, wh = ui.fit_window(int(desired_w * ui._SCALE), int(desired_h * ui._SCALE), sw, sh)
    ww = max(min(ww, sw - 40), min_w)
    wh = max(min(wh, sh - 60), min_h)
    win.geometry(f"{ww}x{wh}+{(sw - ww) // 2}+{max(10, (sh - wh) // 2)}")
    win.minsize(min(min_w, sw - 40), min(min_h, sh - 60))
    _bind_rounded_toplevel(win)


def _bind_toplevel_drag(header_frame, win):
    """Bind le drag-to-move sur un header frame de Toplevel (Labels uniquement)."""
    _d = {"x": 0, "y": 0}
    def _press(e): _d["x"], _d["y"] = e.x_root, e.y_root
    def _drag(e):
        dx, dy = e.x_root - _d["x"], e.y_root - _d["y"]
        _d["x"], _d["y"] = e.x_root, e.y_root
        win.geometry(f"+{win.winfo_x() + dx}+{win.winfo_y() + dy}")
    header_frame.bind("<ButtonPress-1>", _press)
    header_frame.bind("<B1-Motion>", _drag)
    for child in header_frame.winfo_children():
        if isinstance(child, tk.Label):
            child.bind("<ButtonPress-1>", _press)
            child.bind("<B1-Motion>", _drag)


def _apply_rounded_toplevel(win):
    """Applique les coins arrondis à une fenêtre Toplevel."""
    try:
        if not win.winfo_exists():
            return
        HWND = ui._u32.GetParent(win.winfo_id())
        w, h = win.winfo_width(), win.winfo_height()
        if w > 10 and h > 10:
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, 28, 28)
            if hrgn:
                if not ui._u32.SetWindowRgn(HWND, hrgn, True):
                    ctypes.windll.gdi32.DeleteObject(hrgn)
    except Exception as e:
        ui.log_error(e, "apply_rounded_toplevel")


def _bind_rounded_toplevel(win):
    """Bind <Configure> avec debounce pour coins arrondis sur un Toplevel."""
    win._rounded_job = None
    def _sched(e=None):
        if win._rounded_job:
            try: win.after_cancel(win._rounded_job)
            except Exception: pass
        win._rounded_job = win.after(80, lambda: _apply_rounded_toplevel(win))
    win.after(100, lambda: _apply_rounded_toplevel(win))
    win.bind("<Configure>", _sched)


# ─────────────────────────────────────────────────────────────────────────
# Scroll area factory
# ─────────────────────────────────────────────────────────────────────────

def _make_scroll_area(parent, bg):
    """Crée une zone scrollable (Canvas + Scrollbar + Frame intérieur).
    Retourne (canvas, inner_frame, mousewheel_handler)."""
    fs = tk.Frame(parent, bg=bg)
    fs.pack(fill="both", expand=True, padx=max(8, int(16 * ui._SCALE)), pady=4)
    cs = tk.Canvas(fs, bg=bg, highlightthickness=0)
    sb = tk.Scrollbar(fs, orient="vertical", command=cs.yview)
    cs.configure(yscrollcommand=sb.set)
    cs.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(cs, bg=bg)
    cw = cs.create_window((0, 0), window=inner, anchor="nw")

    _sb_vis = [False]
    def _cfg(e):
        cs.configure(scrollregion=cs.bbox("all"))
        cs.itemconfig(cw, width=cs.winfo_width())
        need = inner.winfo_reqheight() > cs.winfo_height()
        if need and not _sb_vis[0]:
            sb.pack(side="right", fill="y")
            _sb_vis[0] = True
        elif not need and _sb_vis[0]:
            sb.pack_forget()
            _sb_vis[0] = False
    inner.bind("<Configure>", _cfg)
    cs.bind("<Configure>", lambda e: cs.itemconfig(cw, width=e.width))

    _mw_accum = [0.0]
    def _mw(e):
        _mw_accum[0] += -e.delta / 120.0
        lines = int(_mw_accum[0])
        if lines:
            cs.yview_scroll(lines, "units")
            _mw_accum[0] -= lines
    cs.bind("<MouseWheel>", _mw)
    inner.bind("<MouseWheel>", _mw)

    return cs, inner, _mw
