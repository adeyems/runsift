# RunSift roadmap

Completed milestone 1: strictly validated local synthetic run bundles, stable job-ID matching, job/status/duration comparison, deterministic JSON reports, CLI exit codes and automated tests.

Completed milestone 2: configurable absolute/percentage duration thresholds, strict boundary rules, zero-baseline handling, visible effective settings and retained raw deltas, with API/CLI regression tests.

Remaining candidate work, to scope against genuine intended use before estimating hours:

- Structured test-case result comparison with explicit handling of missing, skipped and renamed cases.
- Bounded synthetic log excerpts and failure grouping without executing or trusting log content.
- Local run history and trend reports with careful limits on claims about flaky jobs.
- Saved comparison profiles, readable reports, installation packaging and larger-workload checks.

Keep fixtures synthetic and local. Live CI integrations, account credentials and production logs are outside the current milestone. This is ordinary software CI comparison, not AI-model evaluation or benchmarking. No estimate or task count here is a claim of programme eligibility.
