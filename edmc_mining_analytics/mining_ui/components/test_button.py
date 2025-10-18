"""Test button implementation that mirrors EDMC's update button handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

try:  # pragma: no cover - only available inside EDMC runtime
    import tkinter as tk
    from tkinter import ttk
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

from .button_factory import ButtonType, create_theme_button


ButtonCallback = Callable[[Optional[tk.Event]], None]


@dataclass
class TestButtonWidgets:
    """Container for the test button widget."""

    button: ButtonType

    def grid(self, **grid_kwargs: Any) -> None:
        """Grid the underlying widget."""

        self.button.grid(**grid_kwargs)


def create_test_button(
    parent: tk.Widget,
    *,
    command: ButtonCallback,
    text: str = "Test",
    width: int = 12,
) -> TestButtonWidgets:
    """Create a test button that mirrors EDMC's update button setup."""

    button = create_theme_button(
        parent,
        name="edmcma_test_button",
        text=text,
        width=width,
        command=lambda: command(None),
    )

    try:
        button.bind("<Button-1>", command)
    except Exception:
        pass

    return TestButtonWidgets(button=button)


__all__ = ["ButtonCallback", "TestButtonWidgets", "create_test_button"]
