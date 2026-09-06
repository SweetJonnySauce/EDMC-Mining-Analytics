import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from edmc_mining_analytics.journal import JournalProcessor
from edmc_mining_analytics.state import MiningSessionKind, MiningState
from tests.harness_test_utils import (
    load_generated_platinum_session_profile,
    load_test_journal_events,
    resolve_test_location_names,
)


class _SessionRecorderStub:
    def __init__(self) -> None:
        self.start_calls: list[tuple[datetime, str]] = []
        self.end_calls: list[tuple[datetime, str]] = []

    def start_session(self, timestamp: datetime, *, reason: str) -> None:
        self.start_calls.append((timestamp, reason))

    def end_session(self, timestamp: datetime, *, reason: str) -> None:
        self.end_calls.append((timestamp, reason))


class _MarketSearchStub:
    def __init__(self) -> None:
        self.requested_commodities: list[str] = []

    def request_price(self, commodity: str) -> None:
        self.requested_commodities.append(commodity)


class JournalSimulationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = MiningState()
        self._session_started = False
        self._session_start_calls = 0
        self._session_ended = False
        self._refresh_calls = 0

        self.processor = JournalProcessor(
            self.state,
            refresh_ui=self._refresh_ui,
            on_session_start=self._on_session_start,
            on_session_end=self._on_session_end,
            persist_inferred_capacities=lambda: None,
            notify_mining_activity=lambda _reason: None,
            session_recorder=None,
            edsm_client=None,
        )

    def _refresh_ui(self) -> None:
        self._refresh_calls += 1

    def _on_session_start(self) -> None:
        self._session_started = True
        self._session_start_calls += 1

    def _on_session_end(self) -> None:
        self._session_ended = True

    def _timestamp(self, offset_seconds: int) -> str:
        base = datetime(3300, 1, 1, 12, 0, 0)
        return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _cargo_event(self, timestamp: str, *, platinum: int, gold: int, limpets: int = 50) -> dict:
        inventory = [
            {"Name": "Platinum", "Name_Localised": "Platinum", "Count": platinum},
            {"Name": "Gold", "Name_Localised": "Gold", "Count": gold},
            {"Name": "Drones", "Name_Localised": "Limpet", "Count": limpets},
        ]
        return {
            "event": "Cargo",
            "timestamp": timestamp,
            "Inventory": inventory,
            "Count": platinum + gold + limpets,
        }

    def test_rhino_launch_starts_session_with_normalized_type(self) -> None:
        recorder = _SessionRecorderStub()
        state = MiningState()
        session_starts = 0

        def on_session_start() -> None:
            nonlocal session_starts
            session_starts += 1

        processor = JournalProcessor(
            state,
            refresh_ui=lambda: None,
            on_session_start=on_session_start,
            on_session_end=lambda: None,
            persist_inferred_capacities=lambda: None,
            session_recorder=recorder,  # type: ignore[arg-type]
            edsm_client=None,
        )
        launch_timestamp = self._timestamp(0)

        processor.handle_entry({
            "event": "LaunchSRV",
            "SRVType": "  MeV_RhInO  ",
            "timestamp": launch_timestamp,
        })

        self.assertTrue(state.is_mining)
        self.assertEqual(state.mining_start, datetime(3300, 1, 1, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(session_starts, 1)
        self.assertEqual(recorder.start_calls, [(state.mining_start, "Rhino SRV launched")])

    def test_non_rhino_or_malformed_launch_srv_does_not_start_session(self) -> None:
        for srv_type in ("scarab", None, "   ", 1):
            with self.subTest(srv_type=srv_type):
                state = MiningState()
                processor = JournalProcessor(
                    state,
                    refresh_ui=lambda: None,
                    on_session_start=lambda: None,
                    on_session_end=lambda: None,
                    persist_inferred_capacities=lambda: None,
                    edsm_client=None,
                )

                processor.handle_entry({
                    "event": "LaunchSRV",
                    "SRVType": srv_type,
                    "timestamp": self._timestamp(0),
                })

                self.assertFalse(state.is_mining)

    def test_repeated_rhino_launch_preserves_active_session_state(self) -> None:
        self.processor.handle_entry({
            "event": "LaunchSRV",
            "SRVType": "mev_rhino",
            "timestamp": self._timestamp(0),
        })
        original_start = self.state.mining_start
        self.state.cargo_additions["platinum"] = 5

        self.processor.handle_entry({
            "event": "LaunchSRV",
            "SRVType": "MEV_RHINO",
            "timestamp": self._timestamp(30),
        })

        self.assertTrue(self.state.is_mining)
        self.assertEqual(self.state.mining_start, original_start)
        self.assertEqual(self.state.cargo_additions, {"platinum": 5})
        self.assertEqual(self._session_start_calls, 1)

    def test_rhino_dock_ends_active_session_with_journal_timestamp(self) -> None:
        recorder = _SessionRecorderStub()
        state = MiningState()
        session_ends = 0

        def on_session_end() -> None:
            nonlocal session_ends
            session_ends += 1

        processor = JournalProcessor(
            state,
            refresh_ui=lambda: None,
            on_session_start=lambda: None,
            on_session_end=on_session_end,
            persist_inferred_capacities=lambda: None,
            session_recorder=recorder,  # type: ignore[arg-type]
            edsm_client=None,
        )
        processor.handle_entry({
            "event": "LaunchSRV",
            "SRVType": "mev_rhino",
            "timestamp": self._timestamp(0),
        })
        end_calls_before_dock = session_ends
        dock_timestamp = self._timestamp(30)

        processor.handle_entry({
            "event": "DockSRV",
            "SRVType": "  MeV_RhInO  ",
            "timestamp": dock_timestamp,
        })

        expected_end = datetime(3300, 1, 1, 12, 0, 30, tzinfo=timezone.utc)
        self.assertFalse(state.is_mining)
        self.assertEqual(state.mining_end, expected_end)
        self.assertEqual(session_ends, end_calls_before_dock + 1)
        self.assertEqual(recorder.end_calls, [(expected_end, "Rhino SRV docked")])

    def test_invalid_or_inactive_rhino_docks_do_not_end_session(self) -> None:
        recorder = _SessionRecorderStub()
        state = MiningState()
        session_ends = 0

        def on_session_end() -> None:
            nonlocal session_ends
            session_ends += 1

        processor = JournalProcessor(
            state,
            refresh_ui=lambda: None,
            on_session_start=lambda: None,
            on_session_end=on_session_end,
            persist_inferred_capacities=lambda: None,
            session_recorder=recorder,  # type: ignore[arg-type]
            edsm_client=None,
        )
        processor.handle_entry({
            "event": "LaunchSRV",
            "SRVType": "mev_rhino",
            "timestamp": self._timestamp(0),
        })
        original_start = state.mining_start
        end_calls_before_docks = session_ends

        for srv_type in ("scarab", None, "   ", 1):
            with self.subTest(srv_type=srv_type):
                processor.handle_entry({
                    "event": "DockSRV",
                    "SRVType": srv_type,
                    "timestamp": self._timestamp(30),
                })
                self.assertTrue(state.is_mining)
                self.assertEqual(state.mining_start, original_start)
                self.assertIsNone(state.mining_end)
                self.assertEqual(recorder.end_calls, [])
                self.assertEqual(session_ends, end_calls_before_docks)

        inactive_state = MiningState()
        inactive_processor = JournalProcessor(
            inactive_state,
            refresh_ui=lambda: None,
            on_session_start=lambda: None,
            on_session_end=on_session_end,
            persist_inferred_capacities=lambda: None,
            session_recorder=recorder,  # type: ignore[arg-type]
            edsm_client=None,
        )
        inactive_processor.handle_entry({
            "event": "DockSRV",
            "SRVType": "mev_rhino",
            "timestamp": self._timestamp(60),
        })
        self.assertFalse(inactive_state.is_mining)
        self.assertIsNone(inactive_state.mining_end)
        self.assertEqual(recorder.end_calls, [])
        self.assertEqual(session_ends, end_calls_before_docks)

    def test_rhino_launch_after_supercruise_starts_a_fresh_session(self) -> None:
        recorder = _SessionRecorderStub()
        state = MiningState()
        session_starts = 0

        def on_session_start() -> None:
            nonlocal session_starts
            session_starts += 1

        processor = JournalProcessor(
            state,
            refresh_ui=lambda: None,
            on_session_start=on_session_start,
            on_session_end=lambda: None,
            persist_inferred_capacities=lambda: None,
            session_recorder=recorder,  # type: ignore[arg-type]
            edsm_client=None,
        )
        first_start = self._timestamp(0)
        second_start = self._timestamp(60)
        processor.handle_entry({"event": "LaunchSRV", "SRVType": "mev_rhino", "timestamp": first_start})
        processor.handle_entry({"event": "SupercruiseEntry", "timestamp": self._timestamp(30)})
        processor.handle_entry({"event": "LaunchSRV", "SRVType": "mev_rhino", "timestamp": second_start})

        expected_first_end = datetime(3300, 1, 1, 12, 0, 30, tzinfo=timezone.utc)
        expected_second_start = datetime(3300, 1, 1, 12, 1, tzinfo=timezone.utc)
        self.assertTrue(state.is_mining)
        self.assertEqual(state.mining_start, expected_second_start)
        self.assertIsNone(state.mining_end)
        self.assertEqual(session_starts, 2)
        self.assertEqual(recorder.end_calls, [(expected_first_end, "Entered Supercruise")])

    def test_rhino_launch_inherits_planetary_mining_location_from_touchdown(self) -> None:
        self.processor.handle_entry({
            "event": "ApproachBody",
            "Body": "Colonia 3 d",
            "BodyID": 29,
            "timestamp": self._timestamp(0),
        })
        self.processor.handle_entry({
            "event": "Touchdown",
            "Body": "Colonia 3 d",
            "BodyID": 29,
            "NearestDestination": "$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=13;",
            "timestamp": self._timestamp(30),
        })
        self.processor.handle_entry({
            "event": "LaunchSRV",
            "SRVType": "mev_rhino",
            "timestamp": self._timestamp(60),
        })

        self.assertEqual(self.state.mining_location, "Colonia 3 d")
        self.assertEqual(self.state.planetary_mining_location_index, 13)

    def test_invalid_or_expired_planetary_mining_touchdown_is_not_inherited(self) -> None:
        self.processor.handle_entry({
            "event": "ApproachBody",
            "Body": "Colonia 3 d",
            "timestamp": self._timestamp(0),
        })
        self.processor.handle_entry({
            "event": "Touchdown",
            "Body": "Colonia 3 d",
            "NearestDestination": "$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=0;",
            "timestamp": self._timestamp(10),
        })
        self.processor.handle_entry({
            "event": "Touchdown",
            "Body": "Different body",
            "NearestDestination": "$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=13;",
            "timestamp": self._timestamp(20),
        })
        self.processor.handle_entry({
            "event": "Touchdown",
            "Body": "Colonia 3 d",
            "NearestDestination": "$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=13;",
            "timestamp": self._timestamp(30),
        })
        self.processor.handle_entry({
            "event": "SupercruiseEntry",
            "timestamp": self._timestamp(40),
        })
        self.processor.handle_entry({
            "event": "LaunchSRV",
            "SRVType": "mev_rhino",
            "timestamp": self._timestamp(60),
        })

        self.assertIsNone(self.state.mining_location)
        self.assertIsNone(self.state.planetary_mining_location_index)

    def test_active_rhino_session_tracks_planetary_mining_touchdown(self) -> None:
        self.processor.handle_entry({
            "event": "LaunchSRV",
            "SRVType": "mev_rhino",
            "timestamp": self._timestamp(0),
        })
        self.processor.handle_entry({
            "event": "ApproachBody",
            "Body": "Colonia 3 d",
            "timestamp": self._timestamp(10),
        })
        self.processor.handle_entry({
            "event": "Touchdown",
            "Body": "Colonia 3 d",
            "NearestDestination": "$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=13;",
            "timestamp": self._timestamp(20),
        })

        self.assertEqual(self.state.mining_location, "Colonia 3 d")
        self.assertEqual(self.state.planetary_mining_location_index, 13)

    def test_srv_cargo_total_allocates_queued_mixed_refinements(self) -> None:
        self.processor.handle_entry({"event": "LaunchSRV", "SRVType": "mev_rhino", "timestamp": self._timestamp(0)})
        self.processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 0, "timestamp": self._timestamp(1)})
        self.processor.handle_entry({"event": "MiningRefined", "Type": "$uraninite_name;", "Type_Localised": "Uraninite", "timestamp": self._timestamp(2)})
        self.processor.handle_entry({"event": "MiningRefined", "Type": "$silver_name;", "Type_Localised": "Silver", "timestamp": self._timestamp(3)})
        self.processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 2, "timestamp": self._timestamp(4)})
        self.processor.handle_entry({"event": "MiningRefined", "Type": "$uraninite_name;", "Type_Localised": "Uraninite", "timestamp": self._timestamp(5)})
        self.processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 3, "timestamp": self._timestamp(6)})
        self.processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 3, "timestamp": self._timestamp(7)})

        self.assertEqual(self.state.cargo_additions, {"uraninite": 2, "silver": 1})

    def test_srv_cargo_reconciles_out_of_order_counts_at_commodity_transition(self) -> None:
        self.processor.handle_entry({"event": "LaunchSRV", "SRVType": "mev_rhino", "timestamp": self._timestamp(0)})
        self.processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 0, "timestamp": self._timestamp(1)})
        self.processor.handle_entry({"event": "MiningRefined", "Type": "$samarium_name;", "Type_Localised": "Samarium", "timestamp": self._timestamp(2)})
        self.processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 1, "timestamp": self._timestamp(3)})
        self.processor.handle_entry({"event": "MiningRefined", "Type": "$samarium_name;", "Type_Localised": "Samarium", "timestamp": self._timestamp(4)})
        self.processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 1, "timestamp": self._timestamp(5)})

        # A new material makes the unfulfilled Samarium stale. The Cargo delta
        # arrives before the second Copper refinement, as in the Rhino log.
        self.processor.handle_entry({"event": "MiningRefined", "Type": "$copper_name;", "Type_Localised": "Copper", "timestamp": self._timestamp(6)})
        self.processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 3, "timestamp": self._timestamp(7)})
        self.processor.handle_entry({"event": "MiningRefined", "Type": "$copper_name;", "Type_Localised": "Copper", "timestamp": self._timestamp(8)})

        self.assertEqual(self.state.cargo_additions, {"samarium": 1, "copper": 2})

    def test_short_srv_cargo_reconciliation_is_ignored_for_asteroid_sessions(self) -> None:
        self.processor.handle_entry({"event": "LaunchDrone", "Type": "prospector", "timestamp": self._timestamp(0)})
        self.processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 0, "timestamp": self._timestamp(1)})
        self.processor.handle_entry({"event": "MiningRefined", "Type": "$uraninite_name;", "Type_Localised": "Uraninite", "timestamp": self._timestamp(2)})
        self.processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 1, "timestamp": self._timestamp(3)})

        self.assertEqual(self.state.mining_session_kind, MiningSessionKind.ASTEROID)
        self.assertEqual(self.state.cargo_additions, {})

    def test_surface_cargo_reconciliation_requests_estimated_sell_price(self) -> None:
        state = MiningState()
        market_search = _MarketSearchStub()
        processor = JournalProcessor(
            state,
            refresh_ui=lambda: None,
            on_session_start=lambda: None,
            on_session_end=lambda: None,
            persist_inferred_capacities=lambda: None,
            edsm_client=None,
            market_search_service=market_search,  # type: ignore[arg-type]
        )

        processor.handle_entry({"event": "LaunchSRV", "SRVType": "mev_rhino", "timestamp": self._timestamp(0)})
        processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 0, "timestamp": self._timestamp(1)})
        processor.handle_entry({"event": "MiningRefined", "Type": "$gold_name;", "Type_Localised": "Gold", "timestamp": self._timestamp(2)})
        processor.handle_entry({"event": "Cargo", "Vessel": "SRV", "Count": 1, "timestamp": self._timestamp(3)})

        self.assertEqual(state.cargo_totals, {"gold": 1})
        self.assertEqual(state.current_cargo_tonnage, 1)
        self.assertEqual(market_search.requested_commodities, ["gold"])

    def test_session_kind_gates_limpet_tracking_to_asteroid_mining(self) -> None:
        self.processor.handle_entry({"event": "LaunchSRV", "SRVType": "mev_rhino", "timestamp": self._timestamp(0)})
        self.processor.handle_entry({"event": "LaunchDrone", "Type": "collection", "timestamp": self._timestamp(1)})
        self.assertEqual(self.state.mining_session_kind, MiningSessionKind.SURFACE)
        self.assertEqual(self.state.collection_drones_launched, 0)

        asteroid_state = MiningState()
        asteroid_processor = JournalProcessor(asteroid_state, lambda: None, lambda: None, lambda: None, lambda: None)
        asteroid_processor.handle_entry({"event": "LaunchDrone", "Type": "prospector", "timestamp": self._timestamp(2)})
        asteroid_processor.handle_entry({"event": "LaunchDrone", "Type": "collection", "timestamp": self._timestamp(3)})
        self.assertEqual(asteroid_state.mining_session_kind, MiningSessionKind.ASTEROID)
        self.assertEqual(asteroid_state.collection_drones_launched, 1)

    def test_full_prospect_and_material_flow(self) -> None:
        launch_ts = self._timestamp(0)
        self.processor.handle_entry({
            "event": "LaunchDrone",
            "Type": "Prospector",
            "timestamp": launch_ts,
        })

        self.assertTrue(self._session_started)
        self.assertTrue(self.state.is_mining)
        self.assertEqual(self.state.prospector_launched_count, 1)

        baseline_ts = self._timestamp(10)
        self.processor.handle_entry(self._cargo_event(baseline_ts, platinum=0, gold=0))

        prospect_ts = self._timestamp(20)
        self.processor.handle_entry({
            "event": "ProspectedAsteroid",
            "timestamp": prospect_ts,
            "Body": "Test Ring",
            "Content": "High",
            "Materials": [
                {"Name": "Platinum", "Name_Localised": "Platinum", "Proportion": 28.5},
                {"Name": "Gold", "Name_Localised": "Gold", "Proportion": 14.2},
            ],
            "Remaining": 100.0,
        })

        self.assertEqual(self.state.prospected_count, 1)
        self.assertEqual(self.state.prospect_content_counts.get("High"), 1)
        self.assertIn("platinum", self.state.prospected_samples)
        self.assertIn("gold", self.state.prospected_samples)

        cargo_ts = self._timestamp(40)
        self.processor.handle_entry(self._cargo_event(cargo_ts, platinum=5, gold=3))

        self.assertEqual(self.state.cargo_additions.get("platinum"), 5)
        self.assertEqual(self.state.cargo_additions.get("gold"), 3)

        material_events = [
            ("iron", 3),
            ("carbon", 6),
            ("nickel", 9),
        ]
        for idx, (name, count) in enumerate(material_events, start=1):
            self.processor.handle_entry({
                "event": "MaterialCollected",
                "timestamp": self._timestamp(60 + idx),
                "Name": name,
                "Count": count,
            })

        self.assertEqual(self.state.materials_collected.get("iron"), 3)
        self.assertEqual(self.state.materials_collected.get("carbon"), 6)
        self.assertEqual(self.state.materials_collected.get("nickel"), 9)

        platinum_samples = self.state.prospected_samples.get("platinum")
        gold_samples = self.state.prospected_samples.get("gold")
        self.assertIsNotNone(platinum_samples)
        self.assertIsNotNone(gold_samples)
        self.assertIn(28.5, [float(f"{value:.1f}") for value in platinum_samples])
        self.assertIn(14.2, [float(f"{value:.1f}") for value in gold_samples])

        self.assertGreater(self._refresh_calls, 0)

    def test_fsd_jump_stops_active_mining_session(self) -> None:
        launch_ts = self._timestamp(0)
        self.processor.handle_entry({
            "event": "LaunchDrone",
            "Type": "Prospector",
            "StarSystem": "Sol",
            "timestamp": launch_ts,
        })
        self.assertTrue(self.state.is_mining)

        self.processor.handle_entry({
            "event": "FSDJump",
            "StarSystem": "Achenar",
            "timestamp": self._timestamp(30),
        })

        self.assertFalse(self.state.is_mining)
        self.assertTrue(self._session_ended)
        self.assertIsNotNone(self.state.mining_end)

    def test_saa_signals_found_updates_ring_from_body_name(self) -> None:
        self.processor.handle_entry({
            "event": "SAASignalsFound",
            "timestamp": self._timestamp(5),
            "BodyName": "Synuefe UZ-O c22-10 A Ring",
        })
        self.assertEqual(self.state.mining_ring, "Synuefe UZ-O c22-10 A Ring")

    def test_saa_signals_found_ignores_non_ring_body_name(self) -> None:
        self.processor.handle_entry({
            "event": "SAASignalsFound",
            "timestamp": self._timestamp(5),
            "BodyName": "Synuefe UZ-O c22-10 A",
        })
        self.assertIsNone(self.state.mining_ring)

    def test_saa_signals_found_uses_supercruise_exit_ring_confirmation(self) -> None:
        self.processor.handle_entry({
            "event": "SupercruiseExit",
            "timestamp": self._timestamp(5),
            "StarSystem": "Synuefe UZ-O c22-10",
            "Body": "Synuefe UZ-O c22-10 9 A Ring",
            "BodyID": 29,
        })
        self.assertEqual(self.state.mining_ring, "Synuefe UZ-O c22-10 9 A Ring")

        self.processor.handle_entry({
            "event": "SAASignalsFound",
            "timestamp": self._timestamp(6),
            "BodyName": "Synuefe UZ-O c22-10 9 B Ring",
            "BodyID": 30,
        })
        self.assertEqual(self.state.mining_ring, "Synuefe UZ-O c22-10 9 A Ring")

        self.processor.handle_entry({
            "event": "SAASignalsFound",
            "timestamp": self._timestamp(7),
            "BodyName": "Synuefe UZ-O c22-10 9 A Ring",
            "BodyID": 29,
        })
        self.assertEqual(self.state.mining_ring, "Synuefe UZ-O c22-10 9 A Ring")

    def test_mining_start_preserves_recent_supercruise_ring(self) -> None:
        self.processor.handle_entry({
            "event": "SupercruiseExit",
            "timestamp": self._timestamp(5),
            "StarSystem": "Synuefe UZ-O c22-10",
            "Body": "Synuefe UZ-O c22-10 9 A Ring",
            "BodyID": 29,
        })
        self.assertEqual(self.state.mining_ring, "Synuefe UZ-O c22-10 9 A Ring")

        self.processor.handle_entry({
            "event": "LaunchDrone",
            "Type": "Prospector",
            "StarSystem": "Synuefe UZ-O c22-10",
            "timestamp": self._timestamp(10),
        })

        self.assertTrue(self.state.is_mining)
        self.assertEqual(self.state.mining_ring, "Synuefe UZ-O c22-10 9 A Ring")

    def test_replay_sample_journal(self) -> None:
        """Replay a captured journal slice to mirror EDMC runtime behaviour."""

        journal_path = Path(__file__).resolve().parent / "config" / "journal_events.json"
        self.assertTrue(journal_path.exists(), "Sample journal file missing")

        payload = load_test_journal_events(rebase_to_now=True)
        sequence = payload.get("sample_mining_session", [])
        self.assertIsInstance(sequence, list, "sample_mining_session must be a list")
        for entry in sequence:
            self.processor.handle_entry(entry, shared_state=None)

        # Expectations after replaying the sample:
        location_names = resolve_test_location_names()
        profile = load_generated_platinum_session_profile()
        sequence = load_test_journal_events(rebase_to_now=False)["sample_mining_session"]
        expected_collection_launches = sum(
            1
            for entry in sequence
            if entry.get("event") == "LaunchDrone" and entry.get("Type") == "Collection"
        )
        expected_prospector_launches = sum(
            1
            for entry in sequence
            if entry.get("event") == "LaunchDrone" and entry.get("Type") == "Prospector"
        )
        self.assertTrue(self._session_started)
        self.assertTrue(self._session_ended)
        self.assertFalse(self.state.is_mining)
        self.assertIsNotNone(self.state.mining_end)
        self.assertEqual(self.state.current_ship, "Type-11 Prospector")
        self.assertEqual(self.state.cargo_capacity, 256)
        self.assertEqual(self.state.prospector_launched_count, expected_prospector_launches)
        self.assertEqual(self.state.collection_drones_launched, expected_collection_launches)
        self.assertEqual(self.state.prospected_count, profile["asteroid_count"])
        self.assertEqual(self.state.prospect_content_counts.get("High", 0), profile["content_summary"]["High"])
        self.assertEqual(self.state.prospect_content_counts.get("Medium", 0), profile["content_summary"]["Medium"])
        self.assertEqual(self.state.prospect_content_counts.get("Low", 0), profile["content_summary"]["Low"])
        self.assertEqual(self.state.cargo_additions.get("platinum"), 246)
        self.assertEqual(self.state.cargo_additions.get("gold"), 18)
        self.assertEqual(self.state.cargo_additions.get("osmium"), 16)
        self.assertEqual(self.state.cargo_additions.get("silver"), 1)
        self.assertEqual(self.state.materials_collected.get("tin"), 3)
        self.assertEqual(self.state.mining_ring, location_names["ring"])


if __name__ == "__main__":
    unittest.main()
