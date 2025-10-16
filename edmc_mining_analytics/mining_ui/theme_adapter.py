"""Theme utilities for EDMC Mining Analytics UI."""

from __future__ import annotations

from typing import Any, Dict, Optional
from weakref import WeakSet

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
        self._registered_widgets: "WeakSet[tk.Widget]" = WeakSet()
        self._buttons: "WeakSet[tk.Widget]" = WeakSet()
        self._checkbuttons: "WeakSet[tk.Widget]" = WeakSet()
        self._dark_button_style = "EDMCMA.Dark.TButton"
        self._alternate_buttons: Dict[tk.Widget, tk.Widget] = {}
        self._apply_palette(False)
        self._ensure_theme_latest(force=True)

    @property
    def is_dark_theme(self) -> bool:
        self._ensure_theme_latest()
        return self._is_dark_theme

    def register(self, widget: tk.Widget) -> None:
        self._ensure_theme_latest()
        self._bind_theme_listener(widget)
        if self._theme is not None:
            try:
                self._theme.register(widget)
                return
            except Exception:
                pass

        self._registered_widgets.add(widget)
        if isinstance(widget, (tk.Button, ttk.Button, tk.Checkbutton, ttk.Checkbutton)):
            return

        self._apply_widget_style(widget)

    def _apply_widget_style(self, widget: tk.Widget) -> None:
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
        """Return the appropriate default text color.

        - On dark theme: use the plugin's fallback text color to ensure
          readable contrast regardless of EDMC style lookups.
        - On light/default theme: prefer the ttk style's label foreground or
          the system text color so we match EDMC's native appearance (black).
        """
        if not self._is_dark_theme:
            try:
                val = self._style.lookup("TLabel", "foreground")
            except tk.TclError:
                val = None
            if val:
                return val
            return "SystemWindowText"
        return self._fallback_text_fg

    def treeview_style(self) -> str:
        """Return a style name for Treeviews used by this plugin.

        - Uses a plugin-scoped style so we don't clobber EDMC's global styles.
        - In light theme, avoid overriding background/foreground so EDMC's
          default theme remains readable.
        - In dark theme, explicitly set colors for readability.
        """
        style_name = "EDMCMA.Treeview"
        heading_name = f"{style_name}.Heading"

        # Ensure the style objects exist but keep them inheriting defaults
        # unless we're on dark theme.
        try:
            self._style.configure(style_name, rowheight=22)
        except tk.TclError:
            pass

        header_font = (
            self._style.lookup("Treeview.Heading", "font") or ("TkDefaultFont", 9, "bold")
        )

        if self._is_dark_theme:
            background = self.table_background_color()
            foreground = self.table_foreground_color()
            header_bg = self.table_header_background_color()
            header_fg = self.table_header_foreground_color()
            header_hover = self.table_header_hover_color()
            selected_bg = self.button_active_background_color()
            selected_fg = self.button_foreground_color()

            # Configure our scoped style with explicit dark colors
            self._style.configure(
                style_name,
                background=background,
                fieldbackground=background,
                foreground=foreground,
                bordercolor=header_bg,
                borderwidth=0,
                relief=tk.FLAT,
                highlightthickness=0,
            )
            self._style.map(
                style_name,
                background=[("selected", selected_bg)],
                foreground=[("selected", selected_fg)],
            )
            self._style.configure(
                heading_name,
                background=header_bg,
                foreground=header_fg,
                relief="flat",
                borderwidth=0,
                font=header_font,
            )
            self._style.map(
                heading_name,
                background=[("active", header_hover)],
                foreground=[("active", header_fg)],
            )
        else:
            # Light theme: inherit EDMC defaults; only set font to keep header tidy.
            try:
                self._style.configure(heading_name, font=header_font)
            except tk.TclError:
                pass

        return style_name

    def table_background_color(self) -> str:
        # Prefer existing theme value; fall back to a safe default for our palettes.
        val = None
        try:
            val = self._style.lookup("Treeview", "background")
        except tk.TclError:
            val = None
        if not val:
            try:
                val = self._style.lookup("TFrame", "background")
            except tk.TclError:
                val = None
        if val:
            return val
        # If no style-provided value, prefer a neutral system default on light theme
        # to avoid unreadable contrasts.
        if not self._is_dark_theme:
            return "SystemWindow"
        return self._fallback_table_bg

    def table_foreground_color(self) -> str:
        try:
            val = self._style.lookup("Treeview", "foreground")
        except tk.TclError:
            val = None
        if not val:
            try:
                val = self._style.lookup("TLabel", "foreground")
            except tk.TclError:
                val = None
        if val:
            return val
        if not self._is_dark_theme:
            return "SystemWindowText"
        return self._fallback_table_header_fg

    def table_stripe_color(self) -> str:
        # Derive a subtle stripe from the base background. On light theme,
        # keep contrast very low to avoid heavy dark rows.
        base = self.table_background_color()
        factor = 1.08 if self._is_dark_theme else 0.98
        adjusted = self._tint_color(base, factor)
        if adjusted:
            return adjusted
        return self._fallback_table_stripe

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

    def style_button(self, button: tk.Widget) -> None:
        self.register(button)
        self._remember_button_defaults(button)
        self._buttons.add(button)
        self._bind_theme_listener(button)
        self._apply_button_style(button)

    def style_checkbox(self, checkbox: tk.Checkbutton) -> None:
        self.register(checkbox)
        self._checkbuttons.add(checkbox)
        self._bind_theme_listener(checkbox)
        self._apply_checkbox_style(checkbox)

    def enable_dark_theme_alternate(
        self,
        button: tk.Widget,
        *,
        geometry: Dict[str, Any],
        image: Optional[tk.PhotoImage] = None,
    ) -> None:
        if self._theme is None:
            return
        if button in self._alternate_buttons:
            return
        try:
            parent = button.nametowidget(button.winfo_parent())
        except Exception:
            return
        alternate = tk.Label(parent, cursor=str(button.cget("cursor") or ""))
        try:
            alternate.configure(borderwidth=0, highlightthickness=0)
        except tk.TclError:
            pass
        if image is not None:
            try:
                alternate.configure(image=image)
            except tk.TclError:
                pass
        else:
            try:
                alternate.configure(text=button.cget("text"))
            except tk.TclError:
                pass
        try:
            alternate.grid(**geometry)
        except tk.TclError:
            return
        self._theme.register(alternate)
        self._schedule_alternate_refresh(alternate)
        self._bind_theme_listener(alternate)
        self._theme.register_alternate((button, alternate, alternate), dict(geometry))
        self._theme.button_bind(alternate, lambda _evt, btn=button: self._invoke_button(btn), image=image)
        self._alternate_buttons[button] = alternate
        if self._is_dark_theme:
            try:
                button.grid_remove()
            except tk.TclError:
                pass
        else:
            try:
                alternate.grid_remove()
            except tk.TclError:
                pass

    def set_button_text(self, button: tk.Widget, text: str) -> None:
        try:
            button.configure(text=text)
        except tk.TclError:
            pass
        alternate = self._alternate_buttons.get(button)
        if alternate:
            try:
                alternate.configure(text=text)
            except tk.TclError:
                pass

    def get_alternate_button(self, button: tk.Widget) -> Optional[tk.Widget]:
        return self._alternate_buttons.get(button)

    def _schedule_alternate_refresh(self, widget: tk.Widget) -> None:
        if not self._theme:
            return

        def _refresh() -> None:
            if not self._widget_exists(widget):
                return
            try:
                self._theme.update(widget)
            except Exception:
                pass
            self._apply_alternate_palette(widget)

        try:
            widget.after_idle(_refresh)
        except tk.TclError:
            _refresh()

    def _apply_alternate_palette(self, alternate: tk.Widget) -> None:
        if not self._is_dark_theme:
            return
        palette = getattr(self._theme, "current", None)
        if not isinstance(palette, dict):
            return
        mapping = {
            "background": palette.get("background"),
            "foreground": palette.get("foreground"),
            "activebackground": palette.get("activebackground"),
            "activeforeground": palette.get("activeforeground"),
            "highlightbackground": palette.get("background"),
            "highlightcolor": palette.get("highlight"),
        }
        for option, value in mapping.items():
            if value:
                try:
                    alternate.configure(**{option: value})
                except tk.TclError:
                    continue

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

    def _ensure_theme_latest(self, *, force: bool = False) -> None:
        is_dark = self._detect_dark_theme()
        if not force and is_dark == self._is_dark_theme:
            return

        self._apply_palette(is_dark)
        self._is_dark_theme = is_dark
        self._restyle_registered_widgets()
        self._restyle_buttons()
        self._restyle_checkbuttons()
        self._update_button_alternate_visibility()

    def _detect_dark_theme(self) -> bool:
        if self._config is not None:
            for getter in ("get_int", "getint", "get"):
                fn = getattr(self._config, getter, None)
                if fn is None:
                    continue
                try:
                    value = fn("theme")  # type: ignore[call-arg]
                except Exception:
                    continue
                if isinstance(value, str):
                    try:
                        value = int(value)
                    except ValueError:
                        continue
                if isinstance(value, int):
                    return value == 1
        return self._is_dark_theme

    def _apply_palette(self, is_dark: bool) -> None:
        if is_dark:
            dark_text = self._resolve_dark_text()
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
            self._fallback_link_fg = "#268bd2"
            self._configure_dark_button_style()
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
            self._fallback_link_fg = "#0645ad"

    def _resolve_dark_text(self) -> str:
        if self._config is not None:
            for getter in ("get_str", "get", "getint"):
                fn = getattr(self._config, getter, None)
                if fn is None:
                    continue
                try:
                    value = fn("dark_text")  # type: ignore[call-arg]
                except Exception:
                    continue
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return "#f5f5f5"

    def _restyle_registered_widgets(self) -> None:
        for widget in list(self._registered_widgets):
            if not self._widget_exists(widget):
                self._registered_widgets.discard(widget)
                continue
            if isinstance(widget, (tk.Button, ttk.Button, tk.Checkbutton, ttk.Checkbutton)) or widget in self._buttons:
                continue
            self._apply_widget_style(widget)

    def _restyle_buttons(self) -> None:
        for button in list(self._buttons):
            if not self._widget_exists(button):
                self._buttons.discard(button)
                continue
            self._apply_button_style(button)

    def _restyle_checkbuttons(self) -> None:
        for checkbox in list(self._checkbuttons):
            if not self._widget_exists(checkbox):
                self._checkbuttons.discard(checkbox)
                continue
            self._apply_checkbox_style(checkbox)

    def _bind_theme_listener(self, widget: tk.Widget) -> None:
        if getattr(widget, "_edmcma_theme_listener", False):
            return

        def _handle_theme_change(_event: tk.Event) -> None:
            self._ensure_theme_latest()

        try:
            widget.bind("<<ThemeChanged>>", _handle_theme_change, add="+")
            setattr(widget, "_edmcma_theme_listener", True)
        except Exception:
            pass

    def _apply_button_style(self, button: tk.Widget) -> None:
        if not self._widget_exists(button):
            return
        try:
            if self._is_dark_theme:
                self._apply_dark_button_style(button)
            else:
                defaults: dict[str, object] | None = getattr(button, "_edmcma_button_defaults", None)
                if defaults:
                    self._apply_widget_options(button, defaults)
                else:
                    button.configure(
                        background="SystemButtonFace",
                        foreground="#000000",
                        activebackground="#e6e6e6",
                        activeforeground="#000000",
                        relief=tk.RAISED,
                        bd=2,
                        highlightthickness=0,
                    )
                button.configure(padding=(12, 4))
        except tk.TclError:
            pass

    def _apply_checkbox_style(self, checkbox: tk.Checkbutton) -> None:
        if not self._widget_exists(checkbox):
            return
        try:
            if self._is_dark_theme:
                background = self.panel_background_color()
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
            else:
                default_bg = (
                    self._style.lookup("TCheckbutton", "background") or "SystemButtonFace"
                )
                checkbox.configure(
                    background=default_bg,
                    activebackground=default_bg,
                    selectcolor=default_bg,
                    highlightbackground=default_bg,
                    highlightcolor=default_bg,
                    highlightthickness=0,
                    bd=0,
                    relief=tk.FLAT,
                    indicatoron=True,
                )
        except tk.TclError:
            pass

    def _apply_dark_button_style(self, button: tk.Widget) -> None:
        if isinstance(button, ttk.Button):
            self._configure_dark_button_style()
            try:
                button.configure(style=self._dark_button_style, padding=(12, 4))
            except tk.TclError:
                pass
        else:
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

    def _widget_exists(self, widget: tk.Widget) -> bool:
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    def _remember_button_defaults(self, button: tk.Widget) -> None:
        if getattr(button, "_edmcma_button_defaults", None) is not None:
            return
        snapshot: dict[str, object] = {}
        for option in (
            "background",
            "foreground",
            "activebackground",
            "activeforeground",
            "highlightbackground",
            "highlightcolor",
            "highlightthickness",
            "bd",
            "relief",
            "style",
            "padding",
        ):
            try:
                snapshot[option] = button.cget(option)
            except tk.TclError:
                continue
        button._edmcma_button_defaults = snapshot  # type: ignore[attr-defined]

    @staticmethod
    def _apply_widget_options(widget: tk.Widget, options: dict[str, object]) -> None:
        for option, value in options.items():
            try:
                widget.configure(**{option: value})
            except tk.TclError:
                continue

    def _invoke_button(self, button: tk.Widget) -> None:
        try:
            invoke = getattr(button, "invoke", None)
            if callable(invoke):
                invoke()
                return
        except Exception:
            pass
        try:
            command = button.cget("command")
        except tk.TclError:
            return
        if callable(command):
            try:
                command()
            except Exception:
                pass

    def _update_button_alternate_visibility(self) -> None:
        for button, alternate in list(self._alternate_buttons.items()):
            if not self._widget_exists(button) or not self._widget_exists(alternate):
                self._alternate_buttons.pop(button, None)
                continue
            if button.winfo_manager() != "grid" or alternate.winfo_manager() != "grid":
                continue
            if self._is_dark_theme:
                try:
                    button.grid_remove()
                except tk.TclError:
                    pass
                try:
                    alternate.grid()
                    self._schedule_alternate_refresh(alternate)
                except tk.TclError:
                    pass
            else:
                try:
                    alternate.grid_remove()
                except tk.TclError:
                    pass
                try:
                    button.grid()
                except tk.TclError:
                    pass

    def _configure_dark_button_style(self) -> None:
        bg = self.button_background_color()
        fg = self.button_foreground_color()
        active_bg = self.button_active_background_color()
        border = self.button_border_color()
        try:
            self._style.configure(
                self._dark_button_style,
                background=bg,
                foreground=fg,
                bordercolor=border,
                focusthickness=1,
                relief="flat",
                padding=(12, 4),
            )
            self._style.map(
                self._dark_button_style,
                background=[("active", active_bg), ("pressed", active_bg)],
                foreground=[("active", fg), ("disabled", fg)],
                bordercolor=[("focus", border), ("active", border)],
            )
        except tk.TclError:
            pass


__all__ = ["ThemeAdapter"]
