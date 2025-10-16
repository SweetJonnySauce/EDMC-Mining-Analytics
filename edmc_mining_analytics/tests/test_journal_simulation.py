import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from ..journal import JournalProcessor
from ..state import MiningState


class JournalSimulationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = MiningState()
        self._session_started = False
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

    def test_replay_sample_journal(self) -> None:
        """Replay a captured journal slice to mirror EDMC runtime behaviour."""

        journal_path = Path(__file__).resolve().parent / "data" / "sample_journal.jsonl"
        self.assertTrue(journal_path.exists(), "Sample journal file missing")

        with journal_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                payload = json.loads(line.strip())
                self.processor.handle_entry(payload, shared_state=None)

        # Expectations after replaying the sample:
        self.assertTrue(self._session_started)
        self.assertTrue(self.state.is_mining)
        self.assertEqual(self.state.prospector_launched_count, 1)
        self.assertEqual(self.state.prospected_count, 1)
        self.assertEqual(self.state.prospect_content_counts.get("High"), 1)
        self.assertEqual(self.state.cargo_additions.get("platinum"), 5)
        self.assertEqual(self.state.cargo_additions.get("gold"), 3)
        self.assertEqual(self.state.materials_collected.get("iron"), 3)
        self.assertEqual(self.state.materials_collected.get("carbon"), 6)
        self.assertEqual(self.state.materials_collected.get("nickel"), 9)


if __name__ == "__main__":
    unittest.main()
