"""UI utility helpers for EDMC Mining Analytics."""

from __future__ import annotations

from typing import Callable, Optional, Tuple

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
        try:
            columns = tuple(self._tree.cget("columns"))
        except tk.TclError:
            return
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
        try:
            tip = tk.Toplevel(self._tree)
        except tk.TclError:
            return
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        try:
            style = ttk.Style(self._tree)
        except tk.TclError:
            tip.destroy()
            return
        try:
            tree_background = self._tree.cget("background")
        except tk.TclError:
            tree_background = None
        bg = (
            style.lookup("TLabel", "background")
            or style.lookup("TFrame", "background")
            or tree_background
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


class WidgetTooltip:
    """Tooltip helper for standard Tk widgets."""

    def __init__(self, widget: tk.Widget, text: Optional[str] = None, *, hover_predicate: Optional[Callable[[int, int], bool]] = None) -> None:
        self._widget = widget
        self._text: Optional[str] = text
        self._tip: Optional[tk.Toplevel] = None
        self._label: Optional[tk.Label] = None
        self._hover_predicate = hover_predicate

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<Motion>", self._on_motion, add="+")

    def set_text(self, text: Optional[str]) -> None:
        self._text = text or None
        if not self._text:
            self._hide()
        elif self._label is not None:
            try:
                self._label.configure(text=self._text)
            except tk.TclError:
                self._hide()

    def _on_enter(self, event: tk.Event) -> None:  # type: ignore[override]
        self._maybe_show(event)

    def _on_motion(self, event: tk.Event) -> None:  # type: ignore[override]
        self._maybe_show(event)

    def _on_leave(self, _event: tk.Event) -> None:  # type: ignore[override]
        self._hide()

    def _show(self, x: int, y: int) -> None:
        text = self._text
        if not text:
            return
        if self._tip is None:
            try:
                tip = tk.Toplevel(self._widget)
            except tk.TclError:
                return
            tip.wm_overrideredirect(True)
            try:
                tip.wm_attributes("-topmost", True)
            except Exception:
                pass
            fg, bg = self._resolve_colors()
            label = tk.Label(
                tip,
                text=text,
                justify="left",
                background=bg,
                foreground=fg,
                relief=tk.SOLID,
                borderwidth=1,
                padx=6,
                pady=4,
                wraplength=320,
            )
            label.pack()
            self._tip = tip
            self._label = label
        else:
            try:
                if self._label is not None:
                    self._label.configure(text=text)
            except tk.TclError:
                self._hide()
                return
        self._position(x, y)

    def _maybe_show(self, event: tk.Event) -> None:
        if not self._text:
            return
        if self._hover_predicate and not self._hover_predicate(int(event.x), int(event.y)):
            self._hide()
            return
        self._show(event.x_root + 12, event.y_root + 12)

    def _position(self, x: int, y: int) -> None:
        if self._tip is None:
            return
        try:
            self._tip.wm_geometry(f"+{x}+{y}")
        except tk.TclError:
            self._hide()

    def _hide(self) -> None:
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
        self._tip = None
        self._label = None

    def _resolve_colors(self) -> Tuple[str, str]:
        try:
            style = ttk.Style(self._widget)
        except tk.TclError:
            style = ttk.Style()
        bg = (
            style.lookup("TLabel", "background")
            or style.lookup("TFrame", "background")
            or self._widget.cget("background")
            or "#ffffe0"
        )
        fg = style.lookup("TLabel", "foreground") or "#000000"
        return fg, bg
