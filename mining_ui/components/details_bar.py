from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import tkinter as tk
import tkinter.font as tkfont

from tooltip import WidgetTooltip
from mining_ui.theme_adapter import ThemeAdapter


@dataclass
class DetailsBarWidgets:
    frame: tk.Frame
    summary_var: tk.StringVar
    summary_label: tk.Label
    summary_tooltip: WidgetTooltip
    rpm_frame: tk.Frame
    rpm_var: tk.StringVar
    rpm_label: tk.Label
    rpm_title_label: tk.Label
    rpm_tooltip: WidgetTooltip
    rpm_font: Optional[tkfont.Font]


def build_details_bar(
    parent: tk.Widget,
    theme: ThemeAdapter,
    *,
    border: int,
    relief: str,
    hover_predicate: Callable[[tk.Widget, int, int], bool],
) -> DetailsBarWidgets:
    details_bar = tk.Frame(parent, highlightthickness=border, bd=border, relief=relief)
    details_bar.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 6))
    details_bar.columnconfigure(0, weight=1)
    theme.register(details_bar)

    summary_var = tk.StringVar(master=details_bar, value="")
    summary_label = tk.Label(
        details_bar,
        textvariable=summary_var,
        justify="left",
        anchor="w",
    )
    summary_label.grid(row=0, column=0, sticky="ew")
    theme.register(summary_label)
    summary_tooltip = WidgetTooltip(
        summary_label,
        hover_predicate=hover_predicate,
    )

    rpm_frame = tk.Frame(
        details_bar,
        highlightthickness=border,
        bd=border if border else 0,
        relief=relief if border else tk.FLAT,
    )
    rpm_frame.grid(row=0, column=1, sticky="e", padx=(8, 0))
    theme.register(rpm_frame)
    rpm_frame.columnconfigure(0, weight=1)

    rpm_var = tk.StringVar(master=rpm_frame, value="0.0")
    rpm_value = tk.Label(
        rpm_frame,
        textvariable=rpm_var,
        anchor="center",
        justify="center",
    )
    rpm_font: Optional[tkfont.Font] = None
    try:
        base_font = tkfont.nametofont(rpm_value.cget("font"))
        rpm_font = tkfont.Font(font=base_font)
        rpm_font.configure(size=max(18, int(base_font.cget("size")) + 8), weight="bold")
        rpm_value.configure(font=rpm_font)
    except tk.TclError:
        rpm_font = None
    rpm_value.grid(row=0, column=0, sticky="ew")
    theme.register(rpm_value)

    rpm_title = tk.Label(rpm_frame, text="RPM", anchor="center")
    rpm_title.grid(row=1, column=0, sticky="ew", pady=(2, 0))
    theme.register(rpm_title)
    rpm_tooltip = WidgetTooltip(rpm_title)

    return DetailsBarWidgets(
        frame=details_bar,
        summary_var=summary_var,
        summary_label=summary_label,
        summary_tooltip=summary_tooltip,
        rpm_frame=rpm_frame,
        rpm_var=rpm_var,
        rpm_label=rpm_value,
        rpm_title_label=rpm_title,
        rpm_tooltip=rpm_tooltip,
        rpm_font=rpm_font,
    )
