from __future__ import annotations

from datetime import timedelta

from tests.harness_test_utils import REPO_ROOT, harness_context


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


def test_harness_can_replay_named_journal_sequence() -> None:
    with harness_context() as (harness, load, _cfg):
        _register_handler(harness, load)
        harness.load_events("journal_events.json")
        harness.play_sequence("sample_mining_session")

        state = load._plugin.state
        assert state.is_mining is True
        assert state.prospector_launched_count == 1
        assert state.prospected_count == 1
        assert state.prospect_content_counts.get("High") == 1
        assert state.cargo_totals.get("platinum") == 5
        assert state.cargo_totals.get("gold") == 3
        assert state.materials_collected.get("iron") == 3
        assert state.materials_collected.get("carbon") == 6
        assert state.materials_collected.get("nickel") == 9


def test_journal_handler_writes_expected_shared_state_keys() -> None:
    with harness_context() as (harness, load, _cfg):
        _register_handler(harness, load)
        shared_state: dict = {}

        harness.fire_event(_launch_prospector_event("3300-01-01T00:00:00Z"), state=shared_state)

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
        assert expected.issubset(shared_state.keys())
        assert shared_state["edmc_mining_active"] is True
        assert shared_state["edmc_mining_start"] is not None
        assert shared_state["edmc_mining_prospectors_launched"] == 1

        harness.fire_event(
            {"event": "SupercruiseEntry", "StarSystem": "Sol", "timestamp": "3300-01-01T00:03:00Z"},
            state=shared_state,
        )
        assert shared_state["edmc_mining_active"] is False


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
                "ShipType": "krait_mkii",
                "ShipType_Localised": "Krait Mk II",
                "CargoCapacity": 192,
                "timestamp": "3300-01-01T01:00:05Z",
            },
            state={},
        )

        assert "id:77" not in journal._pending_ship_updates
        assert load._plugin.state.current_ship in {"Krait Mk II", "krait_mkii"}
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
