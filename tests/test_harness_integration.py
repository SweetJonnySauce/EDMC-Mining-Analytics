from __future__ import annotations

import json
import logging
import shutil
from datetime import timedelta

from tests.harness_test_utils import (
    REPO_ROOT,
    TESTS_ROOT,
    harness_context,
    load_test_journal_events,
    resolve_test_location_names,
    resolve_test_output_root,
)

logger = logging.getLogger("EDMC.harness_tests")


def _register_handler(harness, load) -> None:
    harness.register_journal_handler(
        load.journal_entry,
        commander="HarnessCmdr",
        system="Sol",
        is_beta=False,
    )


def _launch_prospector_event(timestamp: str) -> dict:
    return {
        "event": "LaunchDrone",
        "Type": "Prospector",
        "StarSystem": "Sol",
        "timestamp": timestamp,
    }


def _cargo_event(timestamp: str, *, platinum: int, gold: int, limpets: int) -> dict:
    return {
        "event": "Cargo",
        "timestamp": timestamp,
        "Inventory": [
            {"Name": "Platinum", "Name_Localised": "Platinum", "Count": platinum},
            {"Name": "Gold", "Name_Localised": "Gold", "Count": gold},
            {"Name": "Drones", "Name_Localised": "Limpet", "Count": limpets},
        ],
        "Count": platinum + gold + limpets,
    }


def test_harness_lifecycle_start_stop_is_repeatable() -> None:
    with harness_context(start_plugin=False) as (harness, load, _cfg):
        _register_handler(harness, load)

        plugin_name = load.plugin_start3(str(REPO_ROOT))
        assert plugin_name == "EDMC Mining Analytics"

        harness.fire_event(_launch_prospector_event("3300-01-01T00:00:00Z"), state={})
        assert load._plugin.state.is_mining is True

        load.plugin_stop()
        assert load._plugin.state.is_mining is False
        assert load._plugin.state.mining_start is None
        assert load._plugin.state.prospector_launched_count == 0

        plugin_name_second = load.plugin_start3(str(REPO_ROOT))
        assert plugin_name_second == "EDMC Mining Analytics"

        harness.fire_event(_launch_prospector_event("3300-01-01T00:02:00Z"), state={})
        assert load._plugin.state.is_mining is True

        load.plugin_stop()
        load.plugin_stop()
        assert load._plugin.state.is_mining is False


def test_harness_option_defaults(monkeypatch) -> None:
    monkeypatch.delenv("EDMCMA_HARNESS_USE_REAL_OUTPUT", raising=False)
    monkeypatch.delenv("EDMCMA_HARNESS_SYSTEM_NAME", raising=False)

    assert resolve_test_output_root() == TESTS_ROOT
    assert resolve_test_location_names() == {
        "system": "Test Ring",
        "body": "Test Ring A 8",
        "ring": "Test Ring A 8 A Ring",
        "exit_system": "Test Ring Exit",
    }


def test_harness_option_overrides(monkeypatch) -> None:
    monkeypatch.setenv("EDMCMA_HARNESS_USE_REAL_OUTPUT", "1")
    monkeypatch.setenv("EDMCMA_HARNESS_SYSTEM_NAME", "Option Ring")

    assert resolve_test_output_root() == REPO_ROOT
    assert resolve_test_location_names() == {
        "system": "Option Ring",
        "body": "Option Ring A 8",
        "ring": "Option Ring A 8 A Ring",
        "exit_system": "Option Ring Exit",
    }

    payload = load_test_journal_events(rebase_to_now=False)
    sequence = payload["sample_mining_session"]
    assert any(
        entry.get("event") == "Location"
        and entry.get("StarSystem") == "Option Ring"
        and entry.get("Body") == "Option Ring A 8"
        for entry in sequence
    )
    assert any(
        entry.get("event") == "SupercruiseExit"
        and entry.get("Body") == "Option Ring A 8 A Ring"
        for entry in sequence
    )
    assert any(
        entry.get("event") == "FSDJump"
        and entry.get("StarSystem") == "Option Ring Exit"
        for entry in sequence
    )


def test_harness_can_replay_named_journal_sequence() -> None:
    with harness_context() as (harness, load, _cfg):
        _register_handler(harness, load)
        harness.load_events("journal_events.json")
        harness.play_sequence("sample_mining_session")

        state = load._plugin.state
        location_names = resolve_test_location_names()
        assert state.is_mining is False
        assert state.mining_end is not None
        assert state.current_ship == "Type-11 Prospector"
        assert state.cargo_capacity == 256
        assert state.prospector_launched_count == 21
        assert state.collection_drones_launched == 27
        assert state.prospected_count == 20
        assert state.prospect_content_counts.get("High", 0) == 0
        assert state.prospect_content_counts.get("Medium") == 6
        assert state.prospect_content_counts.get("Low") == 14
        assert state.cargo_totals.get("platinum") == 246
        assert state.cargo_totals.get("gold") == 18
        assert state.cargo_totals.get("osmium") == 16
        assert state.cargo_totals.get("silver") == 1
        assert state.materials_collected.get("tin") == 3
        assert state.mining_ring == location_names["ring"]
        logger.info(
            "Sample mining session replayed: mining=%s prospected=%s collectors=%s platinum=%s osmium=%s gold=%s silver=%s materials=%s",
            state.is_mining,
            state.prospected_count,
            state.collection_drones_launched,
            state.cargo_totals.get("platinum"),
            state.cargo_totals.get("osmium"),
            state.cargo_totals.get("gold"),
            state.cargo_totals.get("silver"),
            dict(state.materials_collected),
        )


def test_harness_full_mining_run_writes_session_data_file() -> None:
    with harness_context() as (harness, load, _cfg):
        _register_handler(harness, load)

        output_root = resolve_test_output_root()
        location_names = resolve_test_location_names()
        tests_session_dir = output_root / "session_data"
        real_session_dir = REPO_ROOT / "session_data"
        real_session_files_before = sorted(path.name for path in real_session_dir.glob("session_data_*.json"))
        tests_session_dir.mkdir(parents=True, exist_ok=True)
        if output_root != REPO_ROOT:
            for path in tests_session_dir.iterdir():
                if path.name in {".gitkeep", "ring_summary.jsonl", "prospected_asteroid_summary.jsonl"}:
                    continue
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)

        state = load._plugin.state
        state.session_logging_enabled = True
        state.plugin_dir = output_root
        load._plugin.session_recorder._enforce_retention = lambda _directory: None

        harness.load_events("journal_events.json")
        harness.play_sequence("sample_mining_session")

        session_dir = output_root / "session_data"
        assert session_dir == tests_session_dir
        session_files = sorted(session_dir.glob("session_data_*.json"))
        if output_root == REPO_ROOT:
            assert session_files
            session_file = max(session_files, key=lambda path: path.stat().st_mtime_ns)
        else:
            assert len(session_files) == 1
            session_file = session_files[0]

        payload = json.loads(session_file.read_text(encoding="utf-8"))
        meta = payload["meta"]
        commodities = payload["commodities"]
        materials = {row["name"].lower(): row["count"] for row in meta["materials"]}

        assert meta["location"]["ring"] == location_names["ring"]
        assert meta["ship"] == "Type-11 Prospector"
        assert meta["cargo_capacity"] == 256
        assert meta["prospected"]["total"] == 20
        assert meta["prospectors_launched"] == 21
        assert meta["collectors_launched"] == 27
        assert meta["collectors_abandoned"] == 89
        assert meta["limpets_remaining"] == 4
        assert meta["content_summary"] == {"High": 0, "Medium": 6, "Low": 14}
        assert materials == {"tin": 3}
        assert commodities["Platinum"]["gathered"]["tons"] == 246
        assert commodities["Gold"]["gathered"]["tons"] == 18
        assert commodities["Osmium"]["gathered"]["tons"] == 16
        assert commodities["Silver"]["gathered"]["tons"] == 1
        assert len(payload["events"]) == 566
        assert payload["events"][-1]["type"] == "mining_session_stopped"
        assert payload["events"][-1]["details"]["reason"] == "FSD Jump"
        if output_root != REPO_ROOT:
            assert sorted(path.name for path in real_session_dir.glob("session_data_*.json")) == real_session_files_before

        logger.info(
            "Mining run exported session data to %s with %s events and commodities=%s",
            session_file.name,
            len(payload["events"]),
            sorted(commodities),
        )


def test_journal_handler_writes_expected_shared_state_keys() -> None:
    with harness_context() as (harness, load, _cfg):
        _register_handler(harness, load)
        shared_state: dict = {}

        harness.fire_event(_launch_prospector_event("3300-01-01T00:00:00Z"), state=shared_state)
        effective_shared_state = harness.monitor.state

        expected = {
            "edmc_mining_active",
            "edmc_mining_start",
            "edmc_mining_prospected",
            "edmc_mining_cargo",
            "edmc_mining_cargo_totals",
            "edmc_mining_limpets",
            "edmc_mining_collection_drones",
            "edmc_mining_prospect_histogram",
            "edmc_mining_total_tph",
            "edmc_mining_prospectors_launched",
            "edmc_mining_prospectors_lost",
        }
        assert expected.issubset(effective_shared_state.keys())
        assert effective_shared_state["edmc_mining_active"] is True
        assert effective_shared_state["edmc_mining_start"] is not None
        assert effective_shared_state["edmc_mining_prospectors_launched"] == 1

        harness.fire_event(
            {"event": "SupercruiseEntry", "StarSystem": "Sol", "timestamp": "3300-01-01T00:03:00Z"},
            state=shared_state,
        )
        assert harness.monitor.state["edmc_mining_active"] is False
        logger.info(
            "Shared mining state published and then cleared after supercruise entry; active=%s tracked_keys=%s",
            harness.monitor.state["edmc_mining_active"],
            sorted(expected),
        )


def test_prefs_hooks_update_cmdr_and_persist_settings(monkeypatch) -> None:
    with harness_context() as (_harness, load, _cfg):
        import edmc_mining_analytics.plugin as plugin_module
        import edmc_mining_analytics.preferences as preferences_module
        from config import config as edmc_config  # type: ignore[import]

        class FakeFrame:
            def __init__(self, parent):
                self.parent = parent
                self.grid_calls = []

            def grid(self, *args, **kwargs) -> None:
                self.grid_calls.append((args, kwargs))

            def columnconfigure(self, *_args, **_kwargs) -> None:
                return

            def rowconfigure(self, *_args, **_kwargs) -> None:
                return

        class FakeNotebook:
            @staticmethod
            def Frame(parent):
                return FakeFrame(parent)

        monkeypatch.setattr(plugin_module, "nb", FakeNotebook)
        monkeypatch.setattr(preferences_module, "config", edmc_config)

        container = load.plugin_prefs(object(), cmdr="PrefsCmdr", is_beta=False)
        assert isinstance(container, FakeFrame)
        assert load._plugin.state.cmdr_name == "PrefsCmdr"

        load._plugin.state.histogram_bin_size = 17
        load._plugin.state.rate_interval_seconds = 42
        load.prefs_changed("PrefsCmdrUpdated", False)

        assert load._plugin.state.cmdr_name == "PrefsCmdrUpdated"
        assert edmc_config.get("edmc_mining_histogram_bin") == 17
        assert edmc_config.get("edmc_mining_rate_interval") == 42


def test_session_boundaries_and_manual_reset() -> None:
    with harness_context() as (harness, load, _cfg):
        _register_handler(harness, load)

        harness.fire_event(_launch_prospector_event("3300-01-01T00:00:00Z"), state={})
        state = load._plugin.state
        assert state.is_mining is True

        harness.fire_event(
            _cargo_event("3300-01-01T00:01:00Z", platinum=0, gold=0, limpets=50),
            state={},
        )
        harness.fire_event(
            {"event": "SupercruiseEntry", "StarSystem": "Sol", "timestamp": "3300-01-01T00:02:00Z"},
            state={},
        )
        assert state.is_mining is False
        assert state.mining_end is not None

        harness.fire_event(_launch_prospector_event("3300-01-01T00:03:00Z"), state={})
        assert state.is_mining is True
        assert state.prospector_launched_count == 1
        assert state.cargo_additions == {}

        load._plugin._handle_reset_request()
        assert state.is_mining is False
        assert state.mining_start is None
        assert state.prospector_launched_count == 0
        assert state.cargo_additions == {}


def test_session_stops_on_fsd_jump() -> None:
    with harness_context() as (harness, load, _cfg):
        _register_handler(harness, load)

        harness.fire_event(_launch_prospector_event("3300-01-01T00:00:00Z"), state={})
        state = load._plugin.state
        assert state.is_mining is True

        harness.fire_event(
            {
                "event": "FSDJump",
                "StarSystem": "Achenar",
                "StarPos": [67.5, -12.25, 3.0],
                "SystemAddress": 4242424242,
                "timestamp": "3300-01-01T00:02:00Z",
            },
            state={},
        )
        assert state.is_mining is False
        assert state.mining_end is not None


def test_launch_without_system_uses_last_supercruise_exit_starsystem() -> None:
    with harness_context() as (harness, load, _cfg):
        _register_handler(harness, load)

        harness.fire_event(
            {
                "event": "SupercruiseExit",
                "StarSystem": "Col 285 Sector VZ-W b15-0",
                "Body": "Col 285 Sector VZ-W b15-0 1 A Ring",
                "BodyID": 29,
                "BodyType": "Planet",
                "timestamp": "3300-01-01T00:00:00Z",
            },
            state={},
        )

        # Simulate a later unrelated event that overwrites current_system.
        harness.fire_event(
            {
                "event": "Music",
                "StarSystem": "Col 285 Sector RT-Y b14-2",
                "MusicTrack": "Exploration",
                "timestamp": "3300-01-01T00:00:05Z",
            },
            state={},
        )
        assert load._plugin.state.current_system == "Col 285 Sector RT-Y b14-2"
        harness.monitor.state["SystemName"] = None

        # Launch event often does not include a system field; mining should fall back
        # to the most recent SupercruiseExit StarSystem.
        harness.fire_event(
            {
                "event": "LaunchDrone",
                "Type": "Prospector",
                "timestamp": "3300-01-01T00:00:10Z",
            },
            state={},
        )

        assert load._plugin.state.is_mining is True
        assert load._plugin.state.current_system == "Col 285 Sector VZ-W b15-0"


def test_shipyard_swap_pending_update_resolves_on_loadout() -> None:
    with harness_context() as (harness, load, _cfg):
        _register_handler(harness, load)
        journal = load._plugin.journal
        journal._schedule_pending_timeout = lambda: None

        harness.fire_event(
            {
                "event": "ShipyardSwap",
                "ShipID": 77,
                "ShipType": "krait_mkii",
                "ShipType_Localised": "Krait Mk II",
                "timestamp": "3300-01-01T01:00:00Z",
            },
            state={},
        )
        assert "id:77" in journal._pending_ship_updates
        assert load._plugin.state.cargo_capacity is None

        harness.fire_event(
            {
                "event": "Loadout",
                "ShipID": 77,
                "Ship": "krait_mkii",
                "ShipIdent": "",
                "ShipName": "",
                "ShipType": "krait_mkii",
                "ShipType_Localised": "Krait Mk II",
                "CargoCapacity": 192,
                "UnladenMass": 320.0,
                "MaxJumpRange": 22.5,
                "Rebuy": 1500000,
                "Modules": [],
                "timestamp": "3300-01-01T01:00:05Z",
            },
            state={},
        )

        assert "id:77" not in journal._pending_ship_updates
        assert load._plugin.state.current_ship in {"Krait MkII", "Krait Mk II", "krait_mkii"}
        assert load._plugin.state.cargo_capacity == 192
        assert load._plugin.state.cargo_capacity_is_inferred is False


def test_shipyard_swap_timeout_applies_inferred_capacity() -> None:
    with harness_context() as (harness, load, _cfg):
        _register_handler(harness, load)
        journal = load._plugin.journal
        journal._schedule_pending_timeout = lambda: None

        load._plugin.state.inferred_capacity_map["id:99"] = 256

        harness.fire_event(
            {
                "event": "ShipyardSwap",
                "ShipID": 99,
                "ShipType": "python",
                "ShipType_Localised": "Python",
                "timestamp": "3300-01-01T02:00:00Z",
            },
            state={},
        )

        pending = journal._pending_ship_updates["id:99"]
        journal._flush_expired_ship_updates(pending.initiated_at + timedelta(seconds=11))

        assert "id:99" not in journal._pending_ship_updates
        assert load._plugin.state.current_ship in {"Python", "python"}
        assert load._plugin.state.cargo_capacity == 256
        assert load._plugin.state.cargo_capacity_is_inferred is True
