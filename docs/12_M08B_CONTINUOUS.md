# M08B finite seeded sources and scheduled correctness

Daily workflow superseded on2026-11-01 by
[start-once live sources/manual append](16_M08_LIVE_LOCAL.md). Legacy isolated
profiles below remain regression tools. New daily acceptance must exercise public
live-up/generate/check, not infer success from this older runner's results.

The newer owner-approved stable manual workflow is documented in
[15_S02_LOCAL_WORKFLOW.md](15_S02_LOCAL_WORKFLOW.md) and
[tools/s02_data](../tools/s02_data/README.md). It is the everyday local interface;
this document retains the separate isolated RAM acceptance contract/evidence.

Source generation diagrams and subsequent catalog/customer diversity are in
[13_S02_GENERATION.md](13_S02_GENERATION.md). This document's six-order v1 runtime
acceptance remains separate from the newer temporal/diversity acceptance in STATUS.

Subsequent implemented temporal DB-backed source design and diagrams:
[14_S02_TEMPORAL_SOURCE.md](14_S02_TEMPORAL_SOURCE.md). Prepared versions are read
as of time, not directly exposed to collectors as a test event feed. Implemented
under separate commands in [TEMPORAL.md](../test_support/TEMPORAL.md); see STATUS
for actual temporal checks. The v1 RAM-store checks below remain a separate mode.

Finalized before implementation, 2026-10-30. Source v0.1/S01 bytes, mappings,
fingerprints, dbt business ownership and existing DAG/controller behavior stay
fixed. No warehouse DDL or new canonical states. M08C faults/load remain out of scope.

## Environment and fields

Reuse the M08A isolated identity/project/path/credential/resource guard, with an
optional immutable marker `profile = m08b` (absent means legacy m08a).
New B markers also bind integer `interval_seconds=180`; the initial development
marker without this field denotes30s. Retained JSON/logs remain inspectable, but
the frozen-base guard intentionally refuses old markers after a Compose change.
Never seed an M08A S01 volume into S02: acceptance requires a fresh ID/volume. B config:
`seed` integer0..2147483647, `scenario_version=s02-v1`, `profile` baseline or
continuous, `interval_seconds=180`, `deadline_seconds=1800` (shared scheduler/
publication/drain wait budget from campaign start; synchronous operations have
separate per-command timeouts, not a hard30-minute process kill). Initial30s proposal
was revised BEFORE the continuous run: local CLI releases take tens of seconds,
and four full dbt/release paths share one publication coordinator. This finite
correctness profile deliberately avoids offering work faster than this laptop
can release; it is not a load benchmark or a changed production default.
The first scheduled run exposed release-slot starvation at the existing hardcoded
15s wait: one website run exhausted Airflow retries while other channels released.
Necessary B prerequisite: `POLLING_SLOT_WAIT_SECONDS` integer0..600, default15
(approved normal behavior unchanged); B marker `slot_wait_seconds=300` and private
model override300. Source/release locks, business attempts, Airflow retries and
atomic publication are unchanged. Invalid values must fail at DAG parse.
Changing base Compose adds this optional env setting; older frozen-base markers
are intentionally refused afterward. All old attempts were already torn down;
their volumes/logs remain, never adopt/reseed them by rewriting hashes.
New B markers bind boolean `drain_signal=true` (absent/false is legacy no-file
mode, still inspectable when its frozen base/config hashes match).
Finite-run drain prerequisite: new B models alone set `POLLING_DRAIN_FILE` to the exact
private container path `/opt/airflow/state/polling-drain` (already isolated bind).
Default absent means approved normal behavior unchanged. After generation and
scheduled proof, guarded host control creates this signal, the DAG processor
serializes NullTimetables, existing UNPAUSED runs finish, then terminal-success
checks and pause follow. No Airflow restart, task clear, lock stealing or state
forcing. This replaces the earlier pause-before-drain ordering and avoids paused
retry/bookkeeping risks; that earlier run eventually completed, not a proved
permanent outage. C's lifecycle/fault campaigns remain separate. The file is
maintenance control, never test truth.
Fixed small bounds:
2 orders/channel, 2 lines/order, 2 committed waves, 12 source operations; USD only,
zero extra charges, positive seeded quantities1..3, existing mapped products.
Generation is barrier-paced in two waves, NOT a fixed offered requests/sec rate;
actual operation times are retained. There is no unbounded background producer.
No throughput/latency percentile or scale claim. Seed reproduces logical inputs,
not execution timestamps/interleaving. Evidence records actual clocks and image IDs.

Only B models enable `SIMULATOR_MODE=s02` in marketplace services and a random
`S02_CONTROL_TOKEN` there, never in collectors/Airflow/report. S01 remains default.
S02 starts with empty in-memory marketplace stores; authenticated control listener
POST `/s02/upsert` accepts one source document (eBay order+fulfillments, Etsy
receipt), maximum1MiB and100 identities, returns committed identity/version.
Atomic per-entity update under lock; no reset/delete; reject backward/equal-time
conflicting content. Store is intentionally NOT restart-durable in B; that requires
an explicit C design/test. Data listeners expose only the existing read endpoints.
Lists sort by updated time then source ID; lock covers ONE request, not traversal.
Mutable offset pages may move. B bounds mutations, retains overlap and reconciles
again after quiescence; it does not claim vendor snapshot isolation or lost history.

Website writer receives bounded JSON on stdin and appends/upserts source rows in
one transaction, including parent timestamp and child changes. No hard deletion.
It has only website_writer credentials and no ledger mount. Pipeline uses its
unchanged read-only consistent source query. Driver alone reads source templates;
templates are never expected warehouse outputs.

## Independent test evidence / assertions

Host-only append JSONL ledger, exclusive file under ignored test evidence:
`sequence` positive integer, `wave`1/2, `source`, scoped `order_id`, intended source
payload and source time, intended/committed outcome, actual UTC commit/HTTP
response time; an unmatched intention is unconfirmed (not committed), with the
failure retained in the result/command evidence. Delivery rows separately record
message ID/status/omission. Never
mount the ledger into services. An interrupted/failed operation is NOT committed.
Even test-only oneoffs use narrow read-only code/fixture directory mounts in B,
not the whole repository root: `/repo/{tests,ingestion,simulator,orchestration,
transformation,fixtures/s01}`. No `/repo/runtime`, `.env` or `.git` is exposed.
`result.json` records config/hash/code/image IDs, real scheduled run IDs, phase
observations, publications, raw/history/evidence/work totals, assertions, owner
signatures, cleanup and PASS/FAIL. Preserve all failed evidence/volumes.

Oracle uses explicit generator purchase facts, exact Decimal money and supported
state rules independently of dbt. Compare source/account/order/line/currency,
quantities, mapping, state, times and order/line money. Authoritative final read is
through source SQL/HTTP after generation stops, not just the intended ledger.
Observed history must match retained raw source identities/times; ledger transitions
alone are not an entitlement to history. Every published snapshot has raw evidence,
every line has its parent, publication batch and mapping/transform version retained.
Replay/repeated observation grows physical raw audit but not logical versions.
No unsupported delivery/refund/cancellation/shipment allocation is synthesized.

## Bounded profiles / sequence

- Baseline: same seeded purchase/lifecycle inputs, reusable CLI acquisition/release
  for each wave/source, finite reconciliation. No scheduler success claim here.
- Continuous: create wave1 (includes orders created7 days ago but updated now),
  enable website/eBay/inbox once, prove a notified Etsy receipt is fetched/published
  while an omitted receipt is absent. Enable recovery once after that evidence
  barrier. Wait for wave1 publication; then commit wave2 (website canceled but still
  paid, eBay partial blue-line shipping, Etsy shipped with no invented line bridge).
  Signed fresh notifications only for the notified receipt; the omitted one requires
  recovery. No per-cycle trigger/collector/dbt invocation in continuous mode.
- Require at least2 real successful scheduled runs for EACH of website_polling,
  ebay_polling, etsy_inbox AND etsy_recovery, with each wave actually published and
  correlated raw/work/run/batch lineage. Confirm inbox and notification-free recovery
  separately. Pause only TEST DAGs, drain in-flight runs within deadline, compare
  final authoritative source to warehouse, then one explicit CLI replay check.
- Check repeated acquisition, empty windows, distinct scoped IDs and absent duplicate
  versions. Teardown only test containers/network, preserve volume/evidence; compare
  protected owner state. Never stop owner Airflow automatically. Small-VM operator
  stop/restore requires separate owner authorization and final health/pause checks.

CI: bounded integration job in an isolated runner, no owner project present. Explicit
`--ci` refuses ANY owner containers/volumes/networks before and after, instead of
pretending a non-existent owner dataset was hashed. Normal local mode requires
the existing idle owner PG and before/after signatures. Add fixture/offline/unit
regression; remote CI is NOT executed merely by adding YAML. Stop before M08C.
