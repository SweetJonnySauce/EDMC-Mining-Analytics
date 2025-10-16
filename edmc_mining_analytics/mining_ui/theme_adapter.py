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
        self._registered_widgets: "WeakSet[tk.Widget]" = WeakSet()
        self._buttons: "WeakSet[tk.Widget]" = WeakSet()
        self._checkbuttons: "WeakSet[tk.Widget]" = WeakSet()
        self._alternate_buttons: Dict[tk.Widget, tk.Widget] = {}
        self._dark_button_style = "EDMCMA.Dark.TButton"

        self._is_dark_theme = False
        self._apply_palette(False)
        self._ensure_theme_latest(force=True)

    # ------------------------------------------------------------------
    # Theme detection / sync
    # ------------------------------------------------------------------
    @property
    def is_dark_theme(self) -> bool:
        self._ensure_theme_latest()
        return self._is_dark_theme

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
        if self._config is None:
            return self._is_dark_theme
        for getter_name in ("get_int", "getint", "get"):
            getter = getattr(self._config, getter_name, None)
            if getter is None:
                continue
            try:
                value = getter("theme")  # type: ignore[misc]
            except Exception:
                continue
            if isinstance(value, str):
                try:
                    value = int(value.strip())
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
        if self._config is None:
            return "#f5f5f5"
        for getter_name in ("get_str", "get", "getint"):
            getter = getattr(self._config, getter_name, None)
            if getter is None:
                continue
            try:
                value = getter("dark_text")  # type: ignore[misc]
            except Exception:
                continue
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "#f5f5f5"

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------
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

    def _restyle_registered_widgets(self) -> None:
        for widget in list(self._registered_widgets):
            if not self._widget_exists(widget):
                self._registered_widgets.discard(widget)
                continue
            if widget in self._buttons:
                continue
            if isinstance(widget, (tk.Button, ttk.Button, tk.Checkbutton, ttk.Checkbutton)):
                continue
            self._apply_widget_style(widget)

    # ------------------------------------------------------------------
    # Styling primitives
    # ------------------------------------------------------------------
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
        if not self._is_dark_theme:
            try:
                value = self._style.lookup("TLabel", "foreground")
            except tk.TclError:
                value = None
            if value:
                return value
            return "SystemWindowText"
        return self._fallback_text_fg

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

    # ------------------------------------------------------------------
    # Public styling helpers
    # ------------------------------------------------------------------
    def style_button(self, button: tk.Widget) -> None:
        self.register(button)
        self._remember_button_defaults(button)
        self._buttons.add(button)
        self._bind_theme_listener(button)
        if self._theme is not None:
            try:
                self._theme.update(button)
            except Exception:
                pass
            self._schedule_theme_refresh(button)
        else:
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
        existing = self._alternate_buttons.get(button)
        if existing is not None:
            # Refresh any stored geometry/content if caller re-invokes setup.
            self._synchronize_button_content(button, existing)
            self._copy_geometry_attributes(button, existing)
            self._sync_button_state(button, existing)
            self._schedule_theme_refresh(existing)
            self._update_button_alternate_visibility()
            return
        try:
            parent = button.nametowidget(button.winfo_parent())
        except Exception:
            return

        cursor = self._safe_cget(button, "cursor")
        alternate = tk.Label(
            parent,
            cursor=str(cursor or ""),
            borderwidth=0,
            highlightthickness=0,
            relief=tk.FLAT,
        )
        self._synchronize_button_content(button, alternate, image=image)
        self._copy_geometry_attributes(button, alternate)
        self._sync_button_state(button, alternate)
        try:
            alternate.grid(**geometry)
        except tk.TclError:
            alternate.destroy()
            return

        try:
            self._theme.register(alternate)
        except Exception:
            pass
        self._bind_theme_listener(alternate)
        self._theme.register_alternate((button, alternate, alternate), dict(geometry))
        setattr(alternate, "_edmcma_theme_master", button)
        self._register_alternate_relationship(button, alternate)
        self._clone_existing_tooltips(button, alternate)

        self._alternate_buttons[button] = alternate
        self._wrap_button_configure(button)
        self._schedule_theme_refresh(alternate)
        self._schedule_theme_refresh(button)
        image_arg: Any = image if image is not None else getattr(alternate, "_edmcma_button_image", None)
        if image_arg is not None and not hasattr(image_arg, "configure"):
            image_arg = None
        self._theme.button_bind(alternate, lambda _evt, btn=button: self._invoke_button(btn), image=image_arg)
        self._update_button_alternate_visibility()

    def set_button_text(self, button: tk.Widget, text: str) -> None:
        try:
            button.configure(text=text)
        except tk.TclError:
            pass
        alternate = self._alternate_buttons.get(button)
        if alternate is not None:
            try:
                alternate.configure(text=text)
            except tk.TclError:
                pass
            self._copy_geometry_attributes(button, alternate)
            self._schedule_theme_refresh(alternate)

    def get_alternate_button(self, button: tk.Widget) -> Optional[tk.Widget]:
        return self._alternate_buttons.get(button)

    # ------------------------------------------------------------------
    # Internal styling plumbing
    # ------------------------------------------------------------------
    def _apply_button_style(self, button: tk.Widget) -> None:
        if not self._widget_exists(button):
            return
        try:
            if self._is_dark_theme:
                self._apply_dark_button_style(button)
            else:
                defaults: dict[str, Any] | None = getattr(button, "_edmcma_button_defaults", None)
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
                default_bg = self._style.lookup("TCheckbutton", "background") or "SystemButtonFace"
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

    # ------------------------------------------------------------------
    # Alternate management
    # ------------------------------------------------------------------
    def _update_button_alternate_visibility(self) -> None:
        for button, alternate in list(self._alternate_buttons.items()):
            if not self._widget_exists(button):
                self._alternate_buttons.pop(button, None)
                continue
            if not self._widget_exists(alternate):
                self._alternate_buttons.pop(button, None)
                continue

            if self._is_dark_theme:
                # Show alternate label, hide ttk button.
                try:
                    button.grid_remove()
                except tk.TclError:
                    pass
                try:
                    alternate.grid()
                except tk.TclError:
                    pass
                self._synchronize_button_content(button, alternate)
                self._copy_geometry_attributes(button, alternate)
                self._sync_button_state(button, alternate)
                self._apply_alternate_palette(alternate)
                self._schedule_theme_refresh(alternate)
            else:
                # Restore ttk button.
                try:
                    alternate.grid_remove()
                except tk.TclError:
                    pass
                try:
                    button.grid()
                except tk.TclError:
                    pass
                self._schedule_theme_refresh(button)


    def _copy_geometry_attributes(self, source: tk.Widget, target: tk.Widget) -> None:
        pad_x, pad_y = self._extract_padding(source)
        try:
            target.configure(padx=pad_x, pady=pad_y)
        except tk.TclError:
            pass
        try:
            font = source.cget("font")
            if font not in ("", None):
                target.configure(font=font)
        except tk.TclError:
            pass
        for option in ("width", "height"):
            try:
                value = source.cget(option)
            except tk.TclError:
                continue
            if isinstance(value, (int, float)) and value > 0:
                try:
                    target.configure(**{option: value})
                except tk.TclError:
                    continue

    def _synchronize_button_content(
        self,
        button: tk.Widget,
        alternate: tk.Widget,
        *,
        image: Optional[tk.PhotoImage] = None,
    ) -> None:
        textvariable = self._safe_cget(button, "textvariable")
        if textvariable:
            try:
                alternate.configure(textvariable=textvariable)
            except tk.TclError:
                pass
        else:
            text = self._safe_cget(button, "text")
            if text not in (None, ""):
                try:
                    alternate.configure(text=text)
                except tk.TclError:
                    pass

        image_to_use: Any = image if image is not None else self._safe_cget(button, "image")
        if image_to_use not in (None, "", 0):
            try:
                alternate.configure(image=image_to_use)
            except tk.TclError:
                pass
            setattr(alternate, "_edmcma_button_image", image_to_use)
        else:
            try:
                alternate.configure(image="")
            except tk.TclError:
                pass

        for option in ("compound", "underline", "justify", "anchor"):
            value = self._safe_cget(button, option)
            if value not in (None, ""):
                try:
                    alternate.configure(**{option: value})
                except tk.TclError:
                    continue

        font = self._safe_cget(button, "font")
        if font not in (None, ""):
            try:
                alternate.configure(font=font)
            except tk.TclError:
                pass

    def _sync_button_state(self, button: tk.Widget, alternate: tk.Widget) -> None:
        state = self._safe_cget(button, "state")
        if state not in (None, ""):
            try:
                alternate.configure(state=state)
            except tk.TclError:
                pass

    def _register_alternate_relationship(self, button: tk.Widget, alternate: tk.Widget) -> None:
        existing = list(getattr(button, "_edmcma_theme_alternates", ()))
        if alternate not in existing:
            existing.append(alternate)
            setattr(button, "_edmcma_theme_alternates", tuple(existing))

    def _clone_existing_tooltips(self, button: tk.Widget, alternate: tk.Widget) -> None:
        tooltips = list(getattr(button, "_edmcma_tooltips", []))
        for tooltip in tooltips:
            clone_to = getattr(tooltip, "clone_to", None)
            if callable(clone_to):
                try:
                    clone_to(alternate)
                except Exception:
                    continue

    def _wrap_button_configure(self, button: tk.Widget) -> None:
        if getattr(button, "_edmcma_configure_wrapped", None):
            return

        original_configure = button.configure
        original_config = button.config

        def _wrapped_configure(*args: Any, **kwargs: Any) -> Any:
            options = self._extract_config_options(args, kwargs)
            result = original_configure(*args, **kwargs)
            if options:
                self._mirror_alternate_after_config(button, options)
            return result

        def _wrapped_config(*args: Any, **kwargs: Any) -> Any:
            options = self._extract_config_options(args, kwargs)
            result = original_config(*args, **kwargs)
            if options:
                self._mirror_alternate_after_config(button, options)
            return result

        button.configure = _wrapped_configure  # type: ignore[assignment]
        button.config = _wrapped_config  # type: ignore[assignment]
        setattr(button, "_edmcma_configure_wrapped", (original_configure, original_config))

    def _extract_config_options(self, args: tuple[Any, ...], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        if kwargs:
            return dict(kwargs)
        if not args:
            return {}
        first = args[0]
        if isinstance(first, dict):
            return dict(first)
        if len(args) >= 2:
            return {str(first): args[1]}
        return {}

    def _mirror_alternate_after_config(self, button: tk.Widget, options: Dict[str, Any]) -> None:
        alternate = self._alternate_buttons.get(button)
        if alternate is None:
            return
        if "state" in options:
            try:
                alternate.configure(state=options["state"])
            except tk.TclError:
                pass
        if any(key in options for key in ("text", "textvariable", "image", "compound", "underline", "justify", "anchor")):
            self._synchronize_button_content(button, alternate)
        if any(key in options for key in ("padding", "width", "height", "font")):
            self._copy_geometry_attributes(button, alternate)
            font = self._safe_cget(button, "font")
            if font not in (None, ""):
                try:
                    alternate.configure(font=font)
                except tk.TclError:
                    pass
        self._apply_alternate_palette(alternate)
        self._schedule_theme_refresh(alternate)


    def _extract_padding(self, widget: tk.Widget) -> tuple[int, int]:
        default = (12, 4)
        try:
            padding = widget.cget("padding")
        except tk.TclError:
            return default
        values: list[int] = []
        if isinstance(padding, (list, tuple)):
            for item in padding:
                try:
                    values.append(int(float(item)))
                except (TypeError, ValueError):
                    continue
        elif isinstance(padding, str):
            for part in padding.replace(",", " ").split():
                try:
                    values.append(int(float(part)))
                except ValueError:
                    continue
        elif isinstance(padding, (int, float)):
            values = [int(padding)]
        if not values:
            return default
        if len(values) == 1:
            return (values[0], values[0])
        return (values[0], values[1])

    # ------------------------------------------------------------------
    # Misc utilities
    # ------------------------------------------------------------------
    def _apply_alternate_palette(self, alternate: tk.Widget) -> None:
        if not self._is_dark_theme:
            return
        palette: Dict[str, Any] = {}
        if self._theme is not None:
            current = getattr(self._theme, "current", None)
            if isinstance(current, dict):
                palette = current

        background = palette.get("background", self._fallback_panel_bg)
        foreground = palette.get("foreground", self._fallback_button_fg)
        activebackground = palette.get("activebackground", self._fallback_button_active)
        activeforeground = palette.get("activeforeground", self.highlight_text_color())
        highlight = palette.get("highlight", self._fallback_button_border)

        try:
            alternate.configure(
                background=background,
                foreground=foreground,
                activebackground=activebackground,
                activeforeground=activeforeground,
                highlightbackground=background,
                highlightcolor=highlight,
            )
        except tk.TclError:
            pass

    def _safe_cget(self, widget: tk.Widget, option: str) -> Any:
        try:
            return widget.cget(option)
        except tk.TclError:
            return None

    def _schedule_theme_refresh(self, widget: tk.Widget) -> None:
        if not self._theme:
            return

        def _refresh() -> None:
            if not self._widget_exists(widget):
                return
            try:
                self._theme.update(widget)
            except Exception:
                pass

        try:
            widget.after_idle(_refresh)
        except tk.TclError:
            _refresh()

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

    def _restyle_buttons(self) -> None:
        for button in list(self._buttons):
            if not self._widget_exists(button):
                self._buttons.discard(button)
                continue
            if self._theme is not None:
                self._schedule_theme_refresh(button)
            else:
                self._apply_button_style(button)

    def _restyle_checkbuttons(self) -> None:
        for checkbox in list(self._checkbuttons):
            if not self._widget_exists(checkbox):
                self._checkbuttons.discard(checkbox)
                continue
            if self._theme is not None:
                self._schedule_theme_refresh(checkbox)
            else:
                self._apply_checkbox_style(checkbox)

    def _remember_button_defaults(self, button: tk.Widget) -> None:
        if getattr(button, "_edmcma_button_defaults", None) is not None:
            return
        snapshot: dict[str, Any] = {}
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
    def _apply_widget_options(widget: tk.Widget, options: dict[str, Any]) -> None:
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

    def _widget_exists(self, widget: tk.Widget) -> bool:
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    # ------------------------------------------------------------------
    # Button palette helpers
    # ------------------------------------------------------------------
    def table_background_color(self) -> str:
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
        base = self.table_background_color()
        factor = 1.08 if self._is_dark_theme else 0.98
        tinted = self._tint_color(base, factor)
        if tinted:
            return tinted
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


__all__ = ["ThemeAdapter"]
