from __future__ import annotations

import tkinter as tk
from typing import Iterable

DEBUG_BORDER_COLOR = "#ff8800"
DEBUG_CELL_COLOR = "#4a90e2"

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
