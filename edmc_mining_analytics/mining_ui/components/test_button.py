"""Test button implementation that mirrors EDMC's update button handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

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
    """Container for the test button and its themed alternate."""

    button: ttk.Button
    themed_button: tk.Label
    _alternate_registered: bool = field(default=False, init=False, repr=False)

    def grid(self, **grid_kwargs: Any) -> None:
        """Grid both widgets and register the alternate with EDMC's theme helper."""

        self.button.grid(**grid_kwargs)
        if edmc_theme is None:
            # Fallback environment (e.g. tests) – show only the ttk button.
            return

        self.themed_button.grid(**grid_kwargs)
        if not self._alternate_registered:
            edmc_theme.register_alternate(
                (self.button, self.themed_button, self.themed_button),
                dict(grid_kwargs),
            )
            self._alternate_registered = True


def create_test_button(
    parent: tk.Widget,
    *,
    command: ButtonCallback,
    text: str = "Test",
    width: int = 12,
) -> TestButtonWidgets:
    """Create a test button that mirrors EDMC's update button setup."""

    button_kwargs: Dict[str, Any] = {
        "name": "edmcma_test_button",
        "text": text,
        "width": width,
    }

    if edmc_theme is None:
        # Avoid tripping EDMC's theme updater, which doesn't expect ttk buttons with a custom cursor.
        button_kwargs["cursor"] = "hand2"

    button = ttk.Button(parent, **button_kwargs)

    themed_button = tk.Label(
        parent,
        name="edmcma_themed_test_button",
        text=text,
        width=width,
        cursor="hand2",
    )

    if edmc_theme is not None:
        edmc_theme.register(button)
        edmc_theme.register(themed_button)
        button.bind("<Button-1>", command)
        edmc_theme.button_bind(themed_button, command)
    else:
        # Without EDMC's theme helper we fall back to a plain command binding.
        button.configure(command=lambda: command(None))

    return TestButtonWidgets(button=button, themed_button=themed_button)


__all__ = ["ButtonCallback", "TestButtonWidgets", "create_test_button"]
