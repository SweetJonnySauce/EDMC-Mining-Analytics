from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from tests.edmc.mocks import MockConfig

    cfg = MockConfig()
    config_path = REPO_ROOT / "tests" / "config" / "edmc_config.json"
    if config_path.is_file():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                config_data = json.load(f)
            if isinstance(config_data, dict):
                cfg.data.update(config_data)
        except Exception:
            pass
    if not hasattr(cfg, "plugin_dir_path"):
        cfg.plugin_dir_path = REPO_ROOT
    if not hasattr(cfg, "internal_plugin_dir_path"):
        cfg.internal_plugin_dir_path = REPO_ROOT / "tests" / "edmc" / "plugins"
except Exception:
    # Keep bootstrap resilient for environments where EDMC mocks are unavailable.
    pass
