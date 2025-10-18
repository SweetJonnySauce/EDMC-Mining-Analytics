from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from edmc_mining_analytics.tooltip import WidgetTooltip
from ..theme_adapter import ThemeAdapter
from .button_factory import ButtonType, create_theme_button
from .test_button import ButtonCallback, TestButtonWidgets, create_test_button


@dataclass
class TopBarWidgets:
    frame: tk.Frame
    reserve_line: tk.Frame
    status_var: tk.StringVar
    reserve_var: tk.StringVar
    reserve_label: tk.Label
    reserve_warning_label: tk.Label
    version_label: tk.Label
    version_font: Optional[tkfont.Font]
    hotspot_button: ttk.Button
    hotspot_icon: Optional[tk.PhotoImage]
    hotspot_tooltip: WidgetTooltip
    details_toggle: ButtonType
    test_button: TestButtonWidgets


def build_top_bar(
    parent: tk.Widget,
    theme: ThemeAdapter,
    *,
    border: int,
    relief: str,
    plugin_dir: Optional[Path],
    repo_url: str,
    version_text: str,
    on_hotspot: Callable[[], None],
    on_toggle_details: Callable[[], None],
    on_test: ButtonCallback,
    warning_color: str,
) -> TopBarWidgets:
    top_bar = tk.Frame(parent, highlightthickness=border, bd=border, relief=relief)
    top_bar.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))
    top_bar.columnconfigure(0, weight=1)
    theme.register(top_bar)

    status_container = tk.Frame(top_bar, highlightthickness=border, bd=border, relief=relief)
    status_container.grid(row=0, column=0, sticky="ew")
    status_container.columnconfigure(0, weight=1)
    theme.register(status_container)

    status_var = tk.StringVar(master=status_container, value="Not mining")
    status_label = tk.Label(
        status_container,
        textvariable=status_var,
        justify="left",
        anchor="w",
    )
    status_label.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 0))
    status_label.configure(pady=0)
    theme.register(status_label)

    reserve_line = tk.Frame(status_container, highlightthickness=0, bd=0)
    reserve_line.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 0))
    theme.register(reserve_line)

    reserve_var = tk.StringVar(master=reserve_line, value="")
    reserve_label = tk.Label(
        reserve_line,
        textvariable=reserve_var,
        justify="left",
        anchor="w",
    )
    reserve_label.pack(side="left", anchor="w", pady=0)
    reserve_label.configure(pady=0)
    theme.register(reserve_label)

    warning_label = tk.Label(
        reserve_line,
        text="",
        justify="left",
        anchor="w",
    )
    warning_label.pack(side="left", anchor="w", pady=0)
    warning_label.configure(pady=0)
    try:
        base_font = tkfont.nametofont(reserve_label.cget("font"))
        warning_label.configure(font=base_font)
    except tk.TclError:
        pass
    try:
        background = reserve_line.cget("background")
        warning_label.configure(background=background)
    except tk.TclError:
        pass
    warning_label.configure(foreground=warning_color)
    theme.register(warning_label)

    control_cluster = tk.Frame(top_bar, highlightthickness=border, bd=border, relief=relief)
    control_cluster.grid(row=0, column=1, sticky="e")
    control_cluster.columnconfigure(0, weight=0)
    control_cluster.columnconfigure(1, weight=0)
    control_cluster.columnconfigure(2, weight=0)
    control_cluster.columnconfigure(3, weight=0)
    theme.register(control_cluster)

    version_label = tk.Label(control_cluster, text=version_text, anchor="e", cursor="hand2")
    version_font: Optional[tkfont.Font] = None
    try:
        base_font = tkfont.nametofont(version_label.cget("font"))
        version_font = tkfont.Font(font=base_font)
        version_font.configure(underline=True)
        version_label.configure(font=version_font)
    except tk.TclError:
        version_font = None
    version_label.grid(row=0, column=0, padx=(4, 4), pady=0, sticky="e")
    version_label.bind("<Button-1>", lambda _evt: _open_url(repo_url))
    theme.register(version_label)

    hotspot_icon = _load_hotspot_icon(plugin_dir)
    hotspot_button = ttk.Button(
        control_cluster,
        image=hotspot_icon,
        command=on_hotspot,
        cursor="hand2",
    )
    if hotspot_icon is None:
        hotspot_button.configure(text="H", width=3)
    theme.style_button(hotspot_button)
    hotspot_button.grid(row=0, column=1, padx=(0, 4), pady=0, sticky="e")
    theme.enable_dark_theme_alternate(
        hotspot_button,
        geometry={"row": 0, "column": 1, "padx": (0, 4), "pady": 0, "sticky": "e"},
        image=hotspot_icon,
    )
    hotspot_tooltip = WidgetTooltip(hotspot_button, text="Nearby Hotspots")

    details_toggle = create_theme_button(
        control_cluster,
        name="edmcma_details_toggle",
        text="",
        command=on_toggle_details,
    )
    details_toggle.grid(row=0, column=2, padx=0, pady=0, sticky="e")

    test_button_widgets = create_test_button(
        control_cluster,
        command=on_test,
    )
    test_button_widgets.grid(row=0, column=3, padx=(4, 0), pady=0, sticky="e")

    return TopBarWidgets(
        frame=top_bar,
        status_var=status_var,
        reserve_var=reserve_var,
        reserve_label=reserve_label,
        reserve_warning_label=warning_label,
        reserve_line=reserve_line,
        version_label=version_label,
        version_font=version_font,
        hotspot_button=hotspot_button,
        hotspot_icon=hotspot_icon,
        hotspot_tooltip=hotspot_tooltip,
        details_toggle=details_toggle,
        test_button=test_button_widgets,
    )


def _load_hotspot_icon(plugin_dir: Optional[Path]) -> Optional[tk.PhotoImage]:
    icon_path = None
    if plugin_dir:
        candidate = plugin_dir / "assets" / "platinum_hotspot_icon_20x20.png"
        if candidate.exists():
            icon_path = candidate
    if icon_path is None:
        try:
            icon_path = Path(__file__).resolve().parents[2] / "assets" / "platinum_hotspot_icon_20x20.png"
        except Exception:
            icon_path = Path("assets/platinum_hotspot_icon_20x20.png")
    try:
        return tk.PhotoImage(file=str(icon_path))
    except Exception:
        return None


def _open_url(url: str) -> None:
    import webbrowser

    try:
        webbrowser.open(url)
    except Exception:
        pass
