# RunSift roadmap

Completed milestone 1: strictly validated local synthetic run bundles, stable job-ID matching, job/status/duration comparison, deterministic JSON reports, CLI exit codes and automated tests.

Completed milestone 2: configurable absolute/percentage duration thresholds, strict boundary rules, zero-baseline handling, visible effective settings and retained raw deltas, with API/CLI regression tests.

Completed milestone 3: optional structured test cases, stable per-job matching, explicit missing-versus-empty coverage, case status transitions and summaries, examples and compatibility tests.

Remaining candidate work, to scope against genuine intended use before estimating hours:

- Bounded synthetic log excerpts and failure grouping without executing or trusting log content.
- Completed foundation: ordered local history summaries with missing-run coverage. Persistent storage and richer trends remain; no flakiness claims.
- Saved comparison profiles, readable reports, installation packaging and larger-workload checks.

Keep fixtures synthetic and local. Live CI integrations, account credentials and production logs are outside the current milestone. This is ordinary software CI comparison, not AI-model evaluation or benchmarking. No estimate or task count here is a claim of programme eligibility.

Completed follow-up: saved comparison profiles. See README for scope and remaining limitations.

Completed packaging slice: installable wheel and console entry point with isolated installation checks in CI. Public package publication and broader release automation remain future work.

Completed scoped milestone: bounded synthetic failure excerpts. See README for exact semantics and remaining limitations.

Completed scoped follow-up: readable text reports. See README for acceptance scope and remaining limitations.

Completed scoped follow-up: local ordered history summaries. See README for precise behavior and remaining work.

Completed scoped follow-up: explicit local bundle archive. See README for limitations and remaining work.
