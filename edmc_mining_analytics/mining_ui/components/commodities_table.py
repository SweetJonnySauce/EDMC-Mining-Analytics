from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Sequence

import tkinter as tk

from ..theme_adapter import ThemeAdapter


@dataclass
class CommoditiesWidgets:
    header_frame: tk.Frame
    toggle_var: tk.BooleanVar
    toggle: tk.Checkbutton
    table_frame: tk.Frame
    grid_config: Dict[str, Any]
    headers: List[tk.Label] = field(default_factory=list)


def build_commodities_section(
    parent: tk.Widget,
    theme: ThemeAdapter,
    *,
    columns: Sequence[Dict[str, Any]],
    on_toggle: Callable[[], None],
    header_style: Callable[[tk.Label], None],
    initial_visible: bool,
) -> CommoditiesWidgets:
    header_frame = tk.Frame(parent, highlightthickness=0, bd=0)
    header_frame.grid(row=3, column=0, sticky="w", padx=4)
    theme.register(header_frame)

    title = tk.Label(
        header_frame,
        text="Mined Commodities",
        font=(None, 9, "bold"),
        anchor="w",
    )
    title.pack(side="left")
    theme.register(title)

    toggle_var = tk.BooleanVar(master=parent, value=initial_visible)
    toggle = tk.Checkbutton(
        header_frame,
        variable=toggle_var,
        command=on_toggle,
    )
    toggle.pack(side="left", padx=(6, 0))
    theme.register(toggle)
    theme.style_checkbox(toggle)

    table_frame = tk.Frame(parent, highlightthickness=0, bd=0)
    grid_config = {
        "row": 4,
        "column": 0,
        "sticky": "nsew",
        "padx": 4,
        "pady": (2, 6),
    }
    table_frame.grid(**grid_config)
    theme.register(table_frame)

    headers: List[tk.Label] = []
    for idx, column in enumerate(columns):
        table_frame.columnconfigure(idx, weight=column.get("weight", 1))
        header = tk.Label(
            table_frame,
            text=column["label"],
            anchor=column["anchor"],
        )
        header.grid(row=0, column=idx, sticky=column["sticky"], padx=(0, 6), pady=(0, 2))
        theme.register(header)
        header_style(header)
        headers.append(header)

    return CommoditiesWidgets(
        header_frame=header_frame,
        toggle_var=toggle_var,
        toggle=toggle,
        table_frame=table_frame,
        grid_config=grid_config,
        headers=headers,
    )
