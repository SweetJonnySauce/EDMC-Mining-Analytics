# Tests Harness Sync

This project vendors harness sources from:
- `https://github.com/dwomble/EDMC-PluginLib/tree/main/tests`

Vendored paths in this repo:
- `tests/harness.py`
- `tests/edmc/`

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

Do not hand-edit `tests/harness.py` or `tests/edmc/**` after syncing.
