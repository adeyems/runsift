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

A `status_regression` means a matched job went from passed to any non-passed state, including skipped or cancelled. A `status_recovery` is the reverse; neither label proves a code defect was introduced or fixed. Added failures and removed jobs remain visible but are not classified as matched-job regressions. Timing comparison is exact by default, with optional tolerances below and no statistical significance claim. Job durations are not summed into run wall time because jobs may overlap.

JSON reports go to stdout. Exit **0** means no job status/membership differences or duration changes exceeding the configured tolerances, **1** means at least one such difference, and **2** means invalid input or an input-file error (JSON on stderr). Standard argparse usage errors are text on stderr with exit 2. Identical failing runs still match: equality does not mean CI passed. Files are read only, never modified.

## Duration thresholds

```sh
python3 runsift.py examples/baseline.json examples/candidate.json \
  --duration-threshold-ms 100 --duration-threshold-percent 10
```

Both flags default to zero. Milliseconds must be an integer from 0 to 604800000; percentage must be an integer from 0 to 10000. Fractional percentages, negative values and booleans in the Python API are unsupported.

For each matched job, let `delta = candidate_ms - baseline_ms`. A duration change counts only when **both** `abs(delta) > threshold_ms` and `abs(delta) * 100 > baseline_ms * threshold_percent`. The strict comparisons mean equality stays within tolerance. This applies symmetrically to faster and slower jobs, using the baseline as the percentage denominator; reversing the comparison can therefore change the result. Integer cross-multiplication avoids floating-point rounding.

For a 1000 ms baseline, 1100 ms is within a 10% tolerance; 1101 ms exceeds it. With a zero baseline, the percentage allowance is zero, so any nonzero delta exceeds the percentage condition; the absolute threshold can still suppress it. Zero-to-zero is unchanged.

Reports retain raw duration values and signed deltas. `duration_change_exceeds_thresholds` marks a counted timing change; `duration_change_ignored` marks a nonzero delta within tolerance. Both fields are null for unmatched jobs. Effective settings appear in `comparison_rules`. `changed`/`unchanged`, summary counts and exit codes all use these same rules. Status changes and added/removed jobs are never suppressed. The example above still exits 1 because its status and membership changes remain.

## Limits and safety

Use made-up job IDs and data only. Reports include IDs, statuses and timing values; they are not a redaction system. No logs, environment variables, credentials, real customer data or personal data belong in these bundles. The tool makes no network calls, executes no jobs and downloads no artifacts. It has no direct GitHub Actions or other provider integration.

The tool has no test-case/log parsing, history/trends, saved rules or installable package yet. It cannot diagnose why a job failed or establish flakiness from two observations. Thresholds are user-selected tolerances, not evidence that a timing difference is statistically meaningful. See `ROADMAP.md` for candidate work. MIT licensed; no production-readiness or programme-acceptance claim.
