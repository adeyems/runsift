# RunSift

A local command-line tool for developers comparing two synthetic CI-run bundles. See which jobs appeared or disappeared, changed status, or took more or less time. Python 3.10+ standard library only; no dependencies or CI account access.

## Try it

```sh
python3 runsift.py examples/baseline.json examples/candidate.json
python3 -m unittest discover -s tests -v
```

The example intentionally exits 1: `unit` changes from passed to failed and takes 500 ms longer, `legacy` is removed, `integration` is added, and `lint` is unchanged. Comparing the baseline file against itself exits 0.

## Version-1 bundle

```json
{"version": 1, "run_id": "synthetic-42", "jobs": [
  {"id": "unit-python310", "status": "passed", "duration_ms": 1200}
]}
```

These exact fields are required; unknown fields are rejected. IDs must start with an ASCII letter or digit and contain at most 128 ASCII letters, digits, dots, hyphens or underscores. Give matrix jobs distinct stable IDs; matching is exact and does not guess renamed jobs. Run IDs label reports but do not affect equality.

Jobs are finished observations, with status `passed`, `failed`, `skipped` or `cancelled`. Duration is an integer from zero through 604800000 ms (7 days); booleans and fractional values are rejected. Empty job lists are valid. Each bundle allows at most 1000 uniquely named jobs and 2 MiB of UTF-8 JSON. Duplicate keys and non-finite numbers are rejected. This is RunSift's own format, not an importer for a CI vendor's API or logs.

## Comparison rules

Jobs match by ID, independent of input order. Results are sorted by ID and include status/duration on each side, signed duration delta, and added/removed/changed/unchanged classification. Added/removed jobs have null values for their absent side and no duration delta.

A `status_regression` means a matched job went from passed to any non-passed state, including skipped or cancelled. A `status_recovery` is the reverse; neither label proves a code defect was introduced or fixed. Added failures and removed jobs remain visible but are not classified as matched-job regressions. Timing changes are exact, with no tolerance or statistical significance claim. Job durations are not summed into run wall time because jobs may overlap.

JSON reports go to stdout. Exit **0** means no job status/duration or membership differences, **1** means any difference, and **2** means invalid input or an input-file error (JSON on stderr). Standard argparse usage errors are text on stderr with exit 2. Identical failing runs still match: equality does not mean CI passed. Files are read only, never modified.

## Limits and safety

Use made-up job IDs and data only. Reports include IDs, statuses and timing values; they are not a redaction system. No logs, environment variables, credentials, real customer data or personal data belong in these bundles. The tool makes no network calls, executes no jobs and downloads no artifacts. It has no direct GitHub Actions or other provider integration.

Milestone 1 has no test-case/log parsing, history/trends, duration thresholds, saved rules or installable package. It cannot diagnose why a job failed or establish flakiness from two observations. See `ROADMAP.md` for candidate work. MIT licensed; no production-readiness or programme-acceptance claim.
