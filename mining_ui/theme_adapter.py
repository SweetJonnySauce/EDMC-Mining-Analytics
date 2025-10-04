"""Theme utilities for EDMC Mining Analytics UI."""

from __future__ import annotations

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

try:  # pragma: no cover - theme only exists inside EDMC runtime
    from theme import theme as edmc_theme  # type: ignore[import]
except ImportError:  # pragma: no cover
    edmc_theme = None  # type: ignore[assignment]

try:  # pragma: no cover - config only available inside EDMC
    from config import config as edmc_config  # type: ignore[import]
except ImportError:  # pragma: no cover
    edmc_config = None  # type: ignore[assignment]


class ThemeAdapter:
    """Bridge EDMC's theme helper with plain Tk widgets."""

    def __init__(self) -> None:
        self._style = ttk.Style()
        self._theme = edmc_theme
        self._config = edmc_config
        self._is_dark_theme = False
        if self._config is not None:
            try:
                self._is_dark_theme = bool(self._config.get_int("theme") == 1)  # type: ignore[arg-type]
            except Exception:
                self._is_dark_theme = False

        dark_text = None
        if self._config is not None and self._is_dark_theme:
            try:
                dark_text = self._config.get_str("dark_text")  # type: ignore[arg-type]
            except Exception:
                dark_text = None
        if not dark_text:
            dark_text = "#f5f5f5"

        if self._is_dark_theme:
            self._fallback_panel_bg = "#000000"
            self._fallback_text_fg = dark_text
            self._fallback_table_bg = "#000000"
            self._fallback_table_stripe = "#121212"
            self._fallback_table_header_bg = "#000000"
            self._fallback_table_header_fg = dark_text
            self._fallback_table_header_hover = "#1a1a1a"
            self._fallback_button_bg = "#f19a29"
            self._fallback_button_fg = "#1a1005"
            self._fallback_button_active = "#ffb84a"
            self._fallback_button_border = "#ffc266"
            self._fallback_link_fg = "#f8b542"
        else:
            self._fallback_panel_bg = "#0d0d0d"
            self._fallback_text_fg = "#f4bb60"
            self._fallback_table_bg = "#19100a"
            self._fallback_table_stripe = "#23160d"
            self._fallback_table_header_bg = "#3b2514"
            self._fallback_table_header_fg = "#f6e3c0"
            self._fallback_table_header_hover = "#4a2f19"
            self._fallback_button_bg = "#f19a29"
            self._fallback_button_fg = "#1a1005"
            self._fallback_button_active = "#ffb84a"
            self._fallback_button_border = "#ffc266"
            self._fallback_link_fg = "#f7931e"

    @property
    def is_dark_theme(self) -> bool:
        return self._is_dark_theme

    def register(self, widget: tk.Widget) -> None:
        if self._theme is not None:
            try:
                self._theme.register(widget)
                return
            except Exception:
                pass

        background = self.get_background_color(widget)
        try:
            widget.configure(background=background)
        except tk.TclError:
            pass
        for option in ("fg", "foreground"):
            try:
                widget.configure(**{option: self.default_text_color()})
                break
            except tk.TclError:
                continue

    def default_text_color(self) -> str:
        return self._fallback_text_fg

    def treeview_style(self) -> str:
        background = self.table_background_color()
        foreground = self.table_foreground_color()
        header_bg = self.table_header_background_color()
        header_fg = self.table_header_foreground_color()
        header_hover = self.table_header_hover_color()
        header_font = self._style.lookup("Treeview.Heading", "font") or ("TkDefaultFont", 9, "bold")

        selected_bg = self.button_active_background_color()
        selected_fg = self.button_foreground_color()

        self._style.configure(
            "Treeview",
            background=background,
            fieldbackground=background,
            foreground=foreground,
            bordercolor=header_bg,
            borderwidth=0,
            relief=tk.FLAT,
            highlightthickness=0,
            rowheight=22,
        )
        self._style.map(
            "Treeview",
            background=[("selected", selected_bg)],
            foreground=[("selected", selected_fg)],
        )
        self._style.configure(
            "Treeview.Heading",
            background=header_bg,
            foreground=header_fg,
            relief="flat",
            borderwidth=0,
            font=header_font,
        )
        self._style.map(
            "Treeview.Heading",
            background=[("active", header_hover)],
            foreground=[("active", header_fg)],
        )
        return "Treeview"

    def table_background_color(self) -> str:
        return (
            self._style.lookup("Treeview", "background")
            or self._style.lookup("TFrame", "background")
            or self._fallback_table_bg
        )

    def table_foreground_color(self) -> str:
        return (
            self._style.lookup("Treeview", "foreground")
            or self._style.lookup("TLabel", "foreground")
            or self._fallback_table_header_fg
        )

    def table_stripe_color(self) -> str:
        base = self.table_background_color()
        adjusted = self._tint_color(base, 1.08 if self._is_dark_theme else 0.92)
        return adjusted or self._fallback_table_stripe

    def table_header_background_color(self) -> str:
        return self._fallback_table_header_bg

    def table_header_foreground_color(self) -> str:
        return self._fallback_table_header_fg

    def table_header_hover_color(self) -> str:
        return self._fallback_table_header_hover

    def button_background_color(self) -> str:
        return self._fallback_button_bg

    def button_foreground_color(self) -> str:
        return self._fallback_button_fg

    def button_active_background_color(self) -> str:
        return self._fallback_button_active

    def button_border_color(self) -> str:
        return self._fallback_button_border

    def link_color(self) -> str:
        return self._fallback_link_fg

    def panel_background_color(self) -> str:
        return self._fallback_panel_bg

    def highlight_text_color(self) -> str:
        if self._is_dark_theme:
            return "#000000"
        return "#ffffff"

    def get_background_color(self, widget: tk.Widget) -> str:
        style_name = widget.winfo_class()
        for option in ("background", "fieldbackground"):
            try:
                color = self._style.lookup(style_name, option)
            except tk.TclError:
                color = None
            if color:
                return color
        try:
            color = widget.cget("background")  # type: ignore[call-overload]
        except tk.TclError:
            color = None
        if color and color not in {"SystemButtonFace", "SystemWindowBodyColor", "SystemWindow", ""}:
            return color
        return self._fallback_panel_bg

    def style_button(self, button: tk.Button) -> None:
        self.register(button)
        if self._is_dark_theme:
            try:
                button.configure(
                    background=self.button_background_color(),
                    foreground=self.button_foreground_color(),
                    activebackground=self.button_active_background_color(),
                    activeforeground=self.button_foreground_color(),
                    highlightthickness=1,
                    highlightbackground=self.button_border_color(),
                    highlightcolor=self.button_border_color(),
                    bd=0,
                    relief=tk.FLAT,
                    padx=12,
                    pady=4,
                )
            except tk.TclError:
                pass
        else:
            try:
                button.configure(
                    background="SystemButtonFace",
                    foreground="#000000",
                    activebackground="SystemButtonFace",
                    activeforeground="#000000",
                    relief=tk.RAISED,
                    bd=2,
                    highlightthickness=0,
                    padx=12,
                    pady=4,
                )
            except tk.TclError:
                pass

    def style_checkbox(self, checkbox: tk.Checkbutton) -> None:
        self.register(checkbox)
        if not self._is_dark_theme:
            return
        background = self.panel_background_color()
        try:
            checkbox.configure(
                background=background,
                activebackground=background,
                selectcolor=background,
                highlightbackground=background,
                highlightcolor=background,
                highlightthickness=0,
                bd=0,
                relief=tk.FLAT,
                indicatoron=True,
            )
        except tk.TclError:
            pass

    @staticmethod
    def _tint_color(color: str, factor: float) -> str | None:
        if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
            return None
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
        except ValueError:
            return None
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"


__all__ = ["ThemeAdapter"]
