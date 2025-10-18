"""Test button implementation that mirrors EDMC's update button handling."""

from __future__ import annotations

from dataclasses import dataclass
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


ButtonCallback = Callable[[Optional[tk.Event]], None]


@dataclass
class TestButtonWidgets:
    """Container for the test button widget."""

    button: Union[tk.Button, ttk.Button]

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

    if edmc_theme is not None:
        button = tk.Button(
            parent,
            name="edmcma_test_button",
            text=text,
            width=width,
        )
        edmc_theme.register(button)
        button.configure(command=lambda: command(None))
        return TestButtonWidgets(button=button)

    button = ttk.Button(
        parent,
        name="edmcma_test_button",
        text=text,
        width=width,
    )
    # Without EDMC's theme helper we fall back to a plain command binding.
    button.configure(command=lambda: command(None))
    return TestButtonWidgets(button=button)


__all__ = ["ButtonCallback", "TestButtonWidgets", "create_test_button"]
