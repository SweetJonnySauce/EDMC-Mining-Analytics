"""Histogram window helpers for EDMC Mining Analytics UI."""

from __future__ import annotations

from collections import Counter
from typing import Optional, TYPE_CHECKING

try:
    import tkinter as tk
    import tkinter.font as tkfont
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

if TYPE_CHECKING:  # pragma: no cover
    from .main_mining_ui import edmcmaMiningUI

from state import compute_percentage_stats


def open_histogram_window(ui: "edmcmaMiningUI", commodity: str) -> None:
    counter = ui._state.prospected_histogram.get(commodity)
    if not counter:
        return

    window = ui._hist_windows.get(commodity)
    if window and window.winfo_exists():
        canvas = ui._hist_canvases.get(commodity)
        if canvas and canvas.winfo_exists():
            draw_histogram(ui, canvas, commodity)
        window.lift()
        return

    parent = ui._frame
    if parent is None:
        return

    top = tk.Toplevel(parent)
    ui._theme.register(top)
    top.title(f"{ui._format_cargo_name(commodity)} histogram")
    canvas = tk.Canvas(
        top,
        width=360,
        height=260,
        background=ui._theme.table_background_color(),
        highlightthickness=0,
    )
    canvas.pack(fill="both", expand=True)
    ui._theme.register(canvas)
    top.bind(
        "<Configure>",
        lambda event, c=commodity, cv=canvas: draw_histogram(ui, cv, c),
    )
    if not hasattr(canvas, "_theme_change_bound"):
        canvas.bind(
            "<<ThemeChanged>>",
            lambda _evt, c=commodity, cv=canvas: draw_histogram(ui, cv, c),
            add="+",
        )
        canvas._theme_change_bound = True
    draw_histogram(ui, canvas, commodity, counter)
    top.protocol("WM_DELETE_WINDOW", lambda c=commodity: close_histogram_window(ui, c))
    ui._hist_windows[commodity] = top
    ui._hist_canvases[commodity] = canvas


def close_histogram_windows(ui: "edmcmaMiningUI") -> None:
    for commodity in list(ui._hist_windows):
        close_histogram_window(ui, commodity)
    ui._hist_windows.clear()
    ui._hist_canvases.clear()


def close_histogram_window(ui: "edmcmaMiningUI", commodity: str) -> None:
    window = ui._hist_windows.pop(commodity, None)
    ui._hist_canvases.pop(commodity, None)
    if not window:
        return
    try:
        window.destroy()
    except Exception:
        pass


def draw_histogram(
    ui: "edmcmaMiningUI",
    canvas: tk.Canvas,
    commodity: str,
    counter: Optional[Counter[int]] = None,
) -> None:
    canvas.delete("all")
    if counter is None:
        counter = ui._state.prospected_histogram.get(commodity, Counter())
    if not counter:
        canvas.create_text(180, 100, text="No data available")
        return

    if ui._theme.is_dark_theme:
        bg_color = "#000000"
    else:
        bg_color = ui._theme.table_background_color()
    canvas.configure(background=bg_color)

    width = max(1, canvas.winfo_width())
    height = max(1, canvas.winfo_height())
    padding_x = 24
    padding_top = 80
    padding_bottom = 48
    min_height = padding_top + padding_bottom + 1
    if height < min_height:
        height = float(min_height)
    bins = sorted(counter.keys())
    full_range = list(range(bins[0], bins[-1] + 1))
    size = max(1, ui._state.histogram_bin_size)
    labels = {bin_index: ui._format_bin_label(bin_index, size) for bin_index in full_range}

    stats = compute_percentage_stats(ui._state.prospected_samples.get(commodity, []))
    average_percent = stats[1] if stats else None

    label_font = tkfont.nametofont("TkDefaultFont")
    max_label_width = max((label_font.measure(text) for text in labels.values()), default=0)
    min_bin_width = max(48.0, max_label_width + 12.0)
    bin_count = max(1, len(full_range))
    available_width = max(1.0, width - padding_x * 2)
    bin_width = max(min_bin_width, available_width / bin_count)

    heading_text = f"{ui._format_cargo_name(commodity)} histogram"
    if average_percent is not None:
        heading_text += f" — avg {average_percent:.1f}%"
    try:
        title_font = tkfont.nametofont("TkCaptionFont")
    except (tk.TclError, RuntimeError):
        title_font = tkfont.nametofont("TkDefaultFont")
    heading_width = title_font.measure(heading_text) + padding_x * 2

    requested_width = max(padding_x * 2 + bin_width * bin_count, heading_width, 360.0)
    if requested_width > width:
        canvas.config(width=int(requested_width))
        width = requested_width
        available_width = max(1.0, width - padding_x * 2)
        bin_width = max(min_bin_width, available_width / bin_count)

    max_count = max((counter.get(bin_index, 0) for bin_index in full_range), default=0) or 1
    if ui._theme.is_dark_theme:
        text_color = ui._theme.default_text_color()
        bar_color = ui._theme.button_background_color()
    else:
        text_color = ui._theme.table_foreground_color()
        bar_color = "#4a90e2"
    bar_area_height = max(1, height - padding_top - padding_bottom)
    bar_base_y = height - padding_bottom
    label_y = bar_base_y + 6

    canvas.create_text(
        width / 2,
        padding_top / 2,
        text=heading_text,
        fill=text_color,
        font=title_font,
    )

    for idx, bin_index in enumerate(full_range):
        count = counter.get(bin_index, 0)
        x0 = padding_x + idx * bin_width
        x1 = x0 + bin_width * 0.8
        bar_height = bar_area_height * (count / max_count)
        y0 = bar_base_y - bar_height
        y1 = bar_base_y
        canvas.create_rectangle(x0, y0, x1, y1, fill=bar_color, outline=bar_color)
        label = labels[bin_index]
        canvas.create_text((x0 + x1) / 2, label_y, text=label, anchor="n", fill=text_color)
        canvas.create_text((x0 + x1) / 2, y0 - 4, text=str(count), anchor="s", fill=text_color)


def refresh_histogram_windows(ui: "edmcmaMiningUI") -> None:
    for commodity, canvas in list(ui._hist_canvases.items()):
        window = ui._hist_windows.get(commodity)
        if not window or not window.winfo_exists() or not canvas.winfo_exists():
            ui._hist_canvases.pop(commodity, None)
            ui._hist_windows.pop(commodity, None)
            continue
        draw_histogram(ui, canvas, commodity)


def recompute_histograms(ui: "edmcmaMiningUI") -> None:
    from state import recompute_histograms as _recompute  # local import to avoid circular deps

    _recompute(ui._state)


__all__ = [
    "open_histogram_window",
    "close_histogram_windows",
    "close_histogram_window",
    "draw_histogram",
    "refresh_histogram_windows",
    "recompute_histograms",
]
