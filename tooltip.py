"""UI utility helpers for EDMC Mining Analytics."""

from __future__ import annotations

from typing import Optional, Tuple

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc


class TreeTooltip:
    """Simple tooltip helper for Treeview widgets."""

    def __init__(self, tree: ttk.Treeview) -> None:
        self._tree = tree
        self._tip: Optional[tk.Toplevel] = None
        self._cell_texts: dict[Tuple[str, str], str] = {}
        self._heading_texts: dict[str, str] = {}
        self._current_key: Optional[Tuple[str, str]] = None

        tree.bind("<Motion>", self._on_motion, add="+")
        tree.bind("<Leave>", self._hide_tip, add="+")
        tree.bind("<ButtonPress>", self._hide_tip, add="+")

    def clear(self) -> None:
        self._cell_texts.clear()
        self._current_key = None
        self._hide_tip()

    def set_heading_tooltip(self, column_name: str, text: Optional[str]) -> None:
        columns = tuple(self._tree.cget("columns"))
        try:
            idx = columns.index(column_name)
        except ValueError:
            return
        col_id = f"#{idx + 1}"
        if text:
            self._heading_texts[col_id] = text
        else:
            self._heading_texts.pop(col_id, None)

    def set_cell_text(self, item: str, column: str, text: Optional[str]) -> None:
        key = (item, column)
        if text:
            self._cell_texts[key] = text
        elif key in self._cell_texts:
            del self._cell_texts[key]
        if self._current_key == key and not text:
            self._hide_tip()

    def _on_motion(self, event: tk.Event) -> None:  # type: ignore[override]
        region = self._tree.identify_region(event.x, event.y)
        column = self._tree.identify_column(event.x)

        if region == "heading":
            key = ("", column or "")
            if key == self._current_key:
                return
            self._hide_tip()
            heading_text = self._heading_texts.get(column)
            if heading_text:
                self._current_key = key
                x = event.x_root + 16
                y = event.y_root + 12
                self._show_tip(x, y, heading_text)
            return

        item = self._tree.identify_row(event.y)
        key = (item or "", column or "")
        if key == self._current_key:
            return
        self._hide_tip()
        if not item or key not in self._cell_texts:
            return
        self._current_key = key
        x = event.x_root + 16
        y = event.y_root + 12
        self._show_tip(x, y, self._cell_texts[key])

    def _show_tip(self, x: int, y: int, text: str) -> None:
        tip = tk.Toplevel(self._tree)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        style = ttk.Style(self._tree)
        bg = (
            style.lookup("TLabel", "background")
            or style.lookup("TFrame", "background")
            or self._tree.cget("background")
            or "#ffffe0"
        )
        fg = style.lookup("TLabel", "foreground") or "#000000"
        label = tk.Label(
            tip,
            text=text,
            background=bg,
            foreground=fg,
            relief="solid",
            borderwidth=1,
            justify="left",
        )
        label.pack(ipadx=4, ipady=2)
        self._tip = tip

    def _hide_tip(self, *_: object) -> None:
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None
        self._current_key = None
