from __future__ import annotations

import tkinter as tk
from typing import Iterable

DEBUG_BORDER_COLOR = "#ff8800"
DEBUG_CELL_COLOR = "#4a90e2"
DEBUG_EMPTY_CELL_COLOR = "#00b894"

def collect_frames(root: tk.Widget, include_root: bool = True) -> list[tk.Frame]:
    frames: list[tk.Frame] = []
    if include_root and isinstance(root, tk.Frame):
        frames.append(root)
    for child in root.winfo_children():
        frames.extend(collect_frames(child, include_root=True))
    return frames

def apply_frame_debugging(frames: Iterable[tk.Frame]) -> None:
    for frame in frames:
        try:
            frame.configure(
                highlightbackground=DEBUG_BORDER_COLOR,
                highlightcolor=DEBUG_BORDER_COLOR,
                highlightthickness=max(int(frame.cget("highlightthickness") or 0), 1),
                bd=max(int(frame.cget("bd") or 0), 1),
                relief=tk.SOLID,
            )
        except tk.TclError:
            continue
        for child in frame.winfo_children():
            info = child.grid_info()
            if not info:
                continue
            try:
                child.configure(
                    highlightbackground=DEBUG_CELL_COLOR,
                    highlightcolor=DEBUG_CELL_COLOR,
                    highlightthickness=max(int(child.cget("highlightthickness") or 0), 1),
                )
            except tk.TclError:
                continue
        _install_grid_overlays(frame)


def _install_grid_overlays(frame: tk.Frame) -> None:
    if getattr(frame, "_debug_overlays_bound", False):
        _refresh_grid_overlays(frame)
        return

    def _on_configure(event: tk.Event) -> None:
        widget = event.widget
        if isinstance(widget, tk.Frame):
            _refresh_grid_overlays(widget)

    try:
        frame.bind("<Configure>", _on_configure, add="+")
        frame._debug_overlays_bound = True  # type: ignore[attr-defined]
    except tk.TclError:
        return
    frame.after_idle(lambda fr=frame: _refresh_grid_overlays(fr))


def _refresh_grid_overlays(frame: tk.Frame) -> None:
    overlays: list[tk.Widget] = getattr(frame, "_debug_overlays", [])
    for overlay in overlays:
        try:
            overlay.destroy()
        except tk.TclError:
            pass
    frame._debug_overlays = []  # type: ignore[attr-defined]

    try:
        cols, rows = frame.grid_size()
    except tk.TclError:
        return

    if cols <= 0 or rows <= 0:
        return

    occupied = _collect_occupied_cells(frame)
    new_overlays: list[tk.Widget] = []
    for row in range(rows):
        for col in range(cols):
            if (row, col) in occupied:
                continue
            try:
                x, y, width, height = frame.grid_bbox(col, row)
            except tk.TclError:
                continue
            if width <= 0 or height <= 0:
                continue
            overlay = tk.Frame(frame)
            try:
                background = frame.cget("background")
                overlay.configure(background=background)
            except tk.TclError:
                pass
            try:
                overlay.configure(
                    highlightbackground=DEBUG_EMPTY_CELL_COLOR,
                    highlightcolor=DEBUG_EMPTY_CELL_COLOR,
                    highlightthickness=1,
                    bd=0,
                )
            except tk.TclError:
                continue
            overlay.place(x=x, y=y, width=width, height=height)
            new_overlays.append(overlay)

    frame._debug_overlays = new_overlays  # type: ignore[attr-defined]


def _collect_occupied_cells(frame: tk.Frame) -> set[tuple[int, int]]:
    occupied: set[tuple[int, int]] = set()
    try:
        slaves = frame.grid_slaves()
    except tk.TclError:
        return occupied

    for child in slaves:
        info = child.grid_info()
        if not info:
            continue
        row = int(info.get("row", 0))
        column = int(info.get("column", 0))
        rowspan = int(info.get("rowspan", 1))
        columnspan = int(info.get("columnspan", 1))
        for r in range(row, row + rowspan):
            for c in range(column, column + columnspan):
                occupied.add((r, c))
    return occupied
