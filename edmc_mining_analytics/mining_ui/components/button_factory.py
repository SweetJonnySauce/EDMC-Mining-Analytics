"""Factory helpers for creating widgets that cooperate with EDMC's theme."""

from __future__ import annotations

from typing import Any, Callable, Optional, Union

try:  # pragma: no cover - only available inside EDMC runtime
    import tkinter as tk
    from tkinter import ttk
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

try:  # pragma: no cover - EDMC theme helper is only present in runtime
    from theme import theme as edmc_theme  # type: ignore[import]
except ImportError:  # pragma: no cover
    edmc_theme = None  # type: ignore[assignment]

ButtonType = Union[tk.Button, ttk.Button]
CheckboxType = Union[tk.Checkbutton, ttk.Checkbutton]


def create_theme_button(
    parent: tk.Widget,
    *,
    name: str,
    text: str,
    command: Optional[Callable[[], None]] = None,
    width: Optional[int] = None,
) -> ButtonType:
    """Create a button that mirrors EDMC's native update button behaviour."""

    if edmc_theme is not None:
        button = tk.Button(
            parent,
            name=name,
            text=text,
        )
        if width is not None:
            button.configure(width=width)
        if command is not None:
            button.configure(command=command)
        try:
            edmc_theme.register(button)
        except Exception:
            pass
        return button

    button = ttk.Button(
        parent,
        name=name,
        text=text,
    )
    if width is not None:
        button.configure(width=width)
    if command is not None:
        button.configure(command=command)
    return button


def create_theme_checkbox(parent: tk.Widget, **options: Any) -> CheckboxType:
    """Create a checkbox that mirrors EDMC's native styling where possible."""

    if edmc_theme is not None:
        checkbox = tk.Checkbutton(parent, **options)
        try:
            edmc_theme.register(checkbox)
        except Exception:
            pass
        return checkbox

    return ttk.Checkbutton(parent, **options)


__all__ = ["ButtonType", "CheckboxType", "create_theme_button", "create_theme_checkbox"]
