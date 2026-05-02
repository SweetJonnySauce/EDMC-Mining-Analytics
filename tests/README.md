# Tests Harness Sync

This project vendors harness sources from:
- `https://github.com/dwomble/EDMC-PluginLib/tree/main/tests`

Vendored paths in this repo:
- `tests/harness.py`
- `tests/edmc/`
- `tests/journal_config/`

## Important Rule

Treat vendored files as immutable during normal feature work.  
Only update them via a re-vendor sync.

## Sync Command

From repo root:

```bash
./scripts/sync_harness.sh --dry-run
./scripts/sync_harness.sh
```

Or use Make:

```bash
make sync-harness
```

## Pin To A Specific Upstream Ref

```bash
./scripts/sync_harness.sh --ref <branch|tag|commit>
```

Examples:

```bash
./scripts/sync_harness.sh --ref main
./scripts/sync_harness.sh --ref v1.2.3
./scripts/sync_harness.sh --ref a1b2c3d4
```

## Provenance Record

After sync, provenance is written to:
- `tests/VENDORED_HARNESS_SOURCE.md`

It records:
- upstream repo URL
- requested ref
- resolved commit SHA
- sync timestamp (UTC)

## Verify After Sync

Run harness-focused tests first:

```bash
source .venv/bin/activate
python -m pytest tests/test_harness_smoke.py tests/test_harness_integration.py
```

Then run full suite:

```bash
python -m pytest
```

## If Tests Break After Sync

Adjust only non-vendored files (for example):
- `tests/harness_test_utils.py`
- `tests/test_harness_integration.py`
- `tests/session_data/` for non-vendored runtime export fixtures

Do not hand-edit `tests/harness.py` or `tests/edmc/**` after syncing.
Do not hand-edit `tests/journal_config/**` after syncing.

## Runtime Test Artifacts

Normal `pytest`, `make test`, and `make check` runs do not execute the harness session-export path.

When you explicitly run the export helper, harness-generated mining sessions write under:
- `tests/session_data/`

This keeps test-created `session_data_*.json` files separate from the real plugin `session_data/` directory.

## Generate A Test Session

Use the helper script or Makefile target to run the explicit harness export path:

```bash
./scripts/generate_test_session.sh
make generate-test-session
```

Optional flags:

```bash
./scripts/generate_test_session.sh --system-name "My Test System"
./scripts/generate_test_session.sh --real-output
./scripts/generate_test_session.sh --real-output --system-name "My Test System"
```
