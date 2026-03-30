from pathlib import Path

from edmc_mining_analytics.mining_ui.hotspot_search_window import HotspotSearchWindow


def test_save_favorite_rings_creates_config_directory(tmp_path: Path) -> None:
    target = tmp_path / "config" / "hotspot_favorite_rings.json"
    HotspotSearchWindow._save_favorite_rings_file(
        target,
        ["Ring A", "Ring B", "Ring A"],
    )
    assert target.exists()
    loaded = HotspotSearchWindow._load_favorite_rings_file(target)
    assert loaded == {"Ring A", "Ring B"}


def test_load_favorite_rings_handles_missing_file(tmp_path: Path) -> None:
    target = tmp_path / "config" / "hotspot_favorite_rings.json"
    loaded = HotspotSearchWindow._load_favorite_rings_file(target)
    assert loaded == set()


def test_load_favorite_rings_supports_legacy_list_payload(tmp_path: Path) -> None:
    target = tmp_path / "config" / "hotspot_favorite_rings.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('["Ring X", "Ring Y", "Ring X"]', encoding="utf-8")
    loaded = HotspotSearchWindow._load_favorite_rings_file(target)
    assert loaded == {"Ring X", "Ring Y"}
