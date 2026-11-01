# S02 test environment, recovery and load strategy

Daily local workflow revision2026-11-01: [16_M08_LIVE_LOCAL.md](16_M08_LIVE_LOCAL.md).
M08B must additionally verify start-once/manual-append via public CLI on the same
stack, including a second batch without restart and retained earlier facts.
The A isolation harness is for automated regression/fault scopes, not a mandatory
daily environment. The C fault matrix and D measured-load protocol below remain
required; normal/coverage data alone does not implement those failures.

Planning revision: 2026-10-30, owner requested the M08 split and document update.
This is the execution plan, not evidence by itself. M08A isolated baseline and
guards passed local acceptance (see STATUS and
[11_M08A_ISOLATION.md](11_M08A_ISOLATION.md)); owner confirmed completion and
authorized M08B. B passed local case-based checks under
[12_M08B_CONTINUOUS.md](12_M08B_CONTINUOUS.md); owner review pending.
C implementation is tracked in [17_M08C_RECOVERY.md](17_M08C_RECOVERY.md);
all required rows still need evidence. Owner paused C on 2026-11-01 and deferred
D, requesting M09 CV/demo documentation now. This priority exception does not
waive the C/D/full-release runtime acceptance gates below.
M07 checkpoint: `7f459aba8ac2b545ac14b82259a6579bcd25f91b`.
Current task is M09 packaging from a partial checkpoint; STATUS decides runtime PASS.
The existing S01/source contracts, dbt/Airflow requirement and fingerprint rules
remain unchanged. This document takes precedence over older combined M08 scope.

## 1. Delivery sequence and gates

| Part | Deliverable | Entry / exit gate |
| --- | --- | --- |
| M08A | Isolated environment, preflight/safety harness, fresh baseline, offline CI | Existing M07 accepted; isolated bootstrap, negative guards, persistence and protected-environment checks PASS |
| M08B | Seeded source generator, test ledger, bounded continuous correctness, integration CI | A PASS; three source paths reconcile, replay dedupes and each scheduled path has at least two real successes with changing data |
| M08C | Fault matrix, graceful restart, abrupt process loss, pause/resume, recovery runbooks | B PASS; every required case has reproducible automatic/operator outcome and regression PASS |
| M08D | Bounded load/burst/soak, measured limits, evidence-driven fixes | C PASS; declared normal envelope passes correctness/latency/drain limits, stress results honest |
| M09 | Portfolio README/demo/evidence and expanded release CI | D accepted; fresh independent reproduction and packaged checks PASS |

Implement one named part, record actual checks, stop for review. A green baseline
does not certify subsequent fault/load cases. Fix correctness failures before
moving to greater load. Do not require every unsupported recovery to be automatic:
safe terminal failure plus a verified explicit operator procedure can be correct.

## 2. M08A: isolation is more than a Compose project name

- Use a separate explicitly named test project and local test env file (ignored,
  never real credentials). Keep internal source/account IDs valid under existing
  contracts; separate environments, not renamed source identities, isolate S02.
- Override ALL writable paths: PostgreSQL volume, Airflow metadata/state/logs,
  dbt targets/logs and simulator state/ledger/evidence directories. A different
  `--project-name` alone does NOT isolate the current relative bind mounts.
- Use distinct loopback host ports for DB/UI/API/control endpoints, internal
  service-DNS connections and test-only credentials. Inspect resolved Compose
  mounts/networks/ports without printing interpolated secrets. No shared external
  DB volume, writable owner runtime bind, Docker socket in application services
  or public test-control listener. Fault controls are never pipeline credentials.
- Persist a test-environment identity/disposable marker outside the owner dataset.
  Preflight validates marker, project/container/volume labels, resolved paths,
  DB endpoint and run identity. Missing/mismatched identity, owner targets, reused
  ports or escaping paths must fail BEFORE mutation. Allowlist exact test services.
- Reset/kill/fault commands require explicit disposable test scope and resolved
  target verification. No broad prune, wildcard volume removal, owner `down -v`
  or recursive workspace deletion. Default teardown preserves evidence/storage;
  optional reset is a separate guarded action limited to identified test storage.
- Record before/after signatures of protected S01 business/raw/checkpoint state
  while owner pipelines are idle; do not stop/pause them without authorization.
  If owner activity prevents a stable comparison, report the check inconclusive
  and rerun with an agreed quiet window, not a false corruption or PASS claim.
- Bootstrap from fresh isolated storage with the committed migrations. Rerun
  migrations, restart PostgreSQL and verify persistence/roles. Establish the fixed
  S01 baseline in TEST storage with existing runners; do not read owner raw/artifacts
  as prerequisites. Before B, explicitly transition/reseed only disposable test
  storage for S02 so its expected counts never mix with S01 assertions.
- Add offline fixture/utility/compile smoke CI now, with ephemeral credentials,
  bounded jobs and no runtime/secrets checked in. A adds no source generator.

Before coding A, resolve exact overlay/env/runtime paths, marker format, safety
checks, evidence locations, supported local tools and bootstrap order. Finalize
any operational columns/constraints before dependent DDL. Planned names/commands
must not be advertised as runnable until implemented and actually verified.

## 3. S02 profiles and source-generation contract (M08B)

Later proposed prepared-timeline backend:
[14_S02_TEMPORAL_SOURCE.md](14_S02_TEMPORAL_SOURCE.md). Immutable source versions
are selected as of time behind existing marketplace HTTP interfaces, not ingested
directly as scenario truth. V1 RAM behavior and its recorded PASS remain separate.

S02 is a configurable synthetic suite, not a replacement fixed golden dataset:

| Profile | Purpose | Bounds |
| --- | --- | --- |
| Baseline | Small seeded cases, one source then all three, deterministic assertions | Finite declared order/event counts, no faults |
| Continuous | Current-clock source changes without per-cycle commands | Declared rate/mix, max orders/events, duration and drain deadline |
| Fault | One named fault and trigger point at first; combined faults only afterward | Trigger count, retry expectation, recovery deadline and cleanup policy |
| Load / burst / soak | Throughput, saturation, long-run stability | Offered rate, outstanding requests, order/event/byte caps, resource limits, stop conditions |

Run metadata binds seed, generator/scenario version, UTC start, source mix,
operation sequence, initial target size, orders/lines distribution, rate, duration,
polling/overlap/lease/retry settings, fault profile and code/image versions. A seed
reproduces logical inputs/order, NOT exact concurrent interleaving or wall-clock
latency. Record actual sends/commits/responses as evidence too.

- Driver runs outside ingestion/DAGs. Website uses its source writer and atomic
  parent/child updates; collector remains read-only. Marketplaces expose the
  selected HTTP interfaces, never simulator backing storage to the collector.
  Etsy notifications use actual delivery-time signature freshness; receipt state
  is fetched over HTTP and may already be newer than the notification.
- Keep fixed S01 payload bytes/timeline/exports unchanged; changing-source mode is
  opt-in. IDs follow each source's types/endpoint rules and avoid accidental reuse
  within a run. Account identity, mapping version and transformation version remain
  independent; amounts use exact decimal/divisor rules and a declared currency mix.
- Model only supported lifecycle/money/allocation behavior. Independent payment,
  fulfillment and cancellation states; canceled original activity is not revenue,
  refund or deletion. No invented Etsy line/parcel bridge. Any extension of agreed
  source/business behavior must be reviewed before changing the generator/adapter.
- Normal profiles must support old orders updated today, multiline quantities,
  partial shipping where supported, repeated observations and empty windows.
  Missing mapping/unknown enums/equal-time conflicting content are named fault
  cases with policy frozen BEFORE assertions, not silently invented normal rules.
- Mutable pagination does not imply a consistent vendor snapshot. Define simulated
  paging/update behavior and reconciliation assumptions before B. Classify gaps
  outside guarantees honestly; do not treat generated truth as an API history feed.

### Independent oracle and observation-aware reconciliation

The test ledger records intended AND actually committed source operations/delivery
attempts. Only generator/test processes may access it; never mount/read it in
ingestion, dbt, Airflow or report as an input. Keep expected computation independent
of production transformations; version the assertion rules and finite scenarios.

Reconcile by source/account/order/line/currency and like-for-like amount components.
Distinguish generated source transitions, physical acquisitions/deliveries,
deduplicated observed versions, published current state and rejected/pending work.
Repeated transport evidence remains; logical versions do not multiply on replay.
History assertions use actual retained acquisitions, not all ledger transitions.
After generation stops and supported catch-up completes, compare final current
state to a bounded authoritative source read. Never fabricate intermediate states
that changed between polls or before a receipt fetch. Record unrecoverable gaps
and snapshot-history limits separately from a failed current-state reconciliation.

B acceptance includes at least two real scheduled successes per periodic path
(website, eBay, Etsy inbox AND recovery), correlated with generated changes and
source-specific publications; no per-cycle manual triggers. Prove inbox processing
and an omitted-notification recovery case separately. CLI equivalence can be tested
on equivalent retained inputs, not assumed across different live observations.
Add a finite isolated integration CI profile; heavy campaigns remain opt-in.

## 4. Fault/lifecycle matrix (M08C)

Each required row needs source scope, deterministic trigger/barrier, injected fault,
expected automatic/operator outcome, deadline, assertions and run/batch/raw links.
Use handshakes at durable boundaries; timing-only sleeps are not reliable proof.
Cover shared controller once plus source-specific acquisition differences, then
overlapping three-source cycles. Explain any unsupported combination explicitly.

| Case | Required evidence / correct outcome |
| --- | --- |
| Repeated pages, webhook duplicates and old arrivals | Preserve all physical audit; no duplicate logical version/current row; old content cannot silently replace newer state |
| 429/Retry-After, 500, timeout, malformed or mid-page failure | Bounded HTTP/stage attempts; failed windows cannot advance checkpoint as complete; supported resume/replay drains work |
| Omitted, late, reversed and invalid-signature notifications | Signature rejection and delivery audit; valid duplicates dedupe inbox; recovery fetches current receipt without inventing notified states |
| Process loss after raw/inbox persistence, before completion/ack | Durable progress survives; retry/re-delivery safe; no falsely acknowledged unstored webhook |
| Lease expiry with old worker returning | Reclaimed token fences stale completion; bounded attempts and no double-success |
| Loss after freeze or during dbt | Reuse frozen config/manifest; no candidate interleaving; recover or explicitly fail orphaned batch after verifying old worker stopped |
| Failed dbt test / missing mapping / unknown status or version conflict | Explicit exception/failure under existing policy; no made-up mapping/state; last-good publication retained; corrected config uses explicit replay/version lineage |
| Loss during publish vs after commit before acknowledgment | Atomic old-or-new publication; verified committed release safe on retry, no partly published source |
| Exhausted retries and task clear/restart | Durable budgets never reset implicitly; terminal failure visible; new recovery cycle explicitly identified |
| Graceful restart of receiver/worker/Airflow/PostgreSQL | Recorded durable progress and bounded retry behavior; metadata/raw/lease/publication survive |
| Abrupt loss of those processes | Separate from graceful restart; test before/after relevant commits, recover stale state safely; no claim of physical-disk/host-loss durability from container restart |
| Pause/resume while generator advances | Ordinary DAG pause does not kill active tasks; resume catches supported current state/checkpoint gap; missed history remains missing |
| Drain maintenance vs normal pause | Stop new schedules while allowing in-flight retries to finish, then pause; bounded drain timeout and operator recovery if needed |
| Source outage / observer stopped / scheduler stopped | Last-good figures retained; stale/unknown samples and failures visible, never false healthy/complete coverage |

Required cases may be automated recovery OR bounded terminal failure followed by
a tested operator runbook, as declared BEFORE execution. Do not erase failed runs,
steal active locks, force success, rewind checkpoints or reset budgets to get green.
Run S01 and affected M01-M07 regression in isolated scopes after fixes. Any failed
required assertion leaves C incomplete, even if most scenarios passed.

## 5. Load, burst and soak protocol (M08D)

Freeze the test manifest before a campaign: hardware/allocated CPU/RAM, software,
source mix, initial retained history + current orders/lines, payload distribution,
rates/duration, polling settings, target latency/backlog/drain limits and resource
ceilings. Numeric settings are selected after A-C baseline measurement and recorded
before each run; there is no currently measured universal safe rate or capacity.

1. Run the finite correctness baseline, then a low sustained rate on one source
   and all three together. Include a warm-history case, not only empty databases.
2. Increase offered rate in finite steps. Record offered, actually committed and
   processed rates separately; a slow generator must not look like fast ingestion.
3. Run a bounded burst, stop/throttle generation and measure backlog drain, with
   final-state/lineage/money reconciliation after quiescence.
4. Run a predeclared soak long enough for repeated polls/builds/lease renewals and
   artifact growth; report exact duration. A two-cycle demo is not a soak result.
5. Optional stress-to-ceiling is explicit opt-in. Do not require unlimited load
   to PASS; saturation with bounded rejection/backpressure may be a valid limit.
6. Compare baseline, fix one identified bottleneck, rerun SAME workload/regressions.
   Keep before/after evidence. If an incremental model or release-lineage redesign
   is necessary, first define a separately reviewable field/semantic/acceptance
   scope. Never drop tests or weaken atomic publication merely to improve speed.

### Measurements and stop conditions

- Generated logical orders/updates versus actual committed source operations,
  HTTP pages/details/webhook deliveries and distinct observed/published versions.
  Count unique business identities separately; replay/stage attempts are not new
  order throughput. Stratify by channel, workload and validation mode.
- End-to-end source-commit to first matching publication latency p50/p95, sample
  count, failures and unobserved/censored samples. M07 has NO per-order first-
  publication ledger: design reliable test measurement in B/D before claiming
  this metric; don't substitute batch duration or source-created time.
- Stage execution vs slot wait, backlog/oldest known age, error/retry counts,
  budget exhaustion and drain time. Preserve Unknown for missing old clocks.
- Container/host CPU/RAM, DB size/free disk, raw/artifact growth and dashboard
  query/interaction latency separately. M07's 100k target-query benchmark does
  NOT certify source ingestion or million-order processing.
- Predeclare finite request concurrency, total orders/events/bytes, wall timeout,
  CPU/RAM/disk/backlog ceilings and operator stop. Reaching a safety ceiling stops
  generation first; retain logs/state and attempt bounded drain, do not delete
  evidence. Record timeouts and unresolved work rather than silently extending
  deadlines. Invalid safety configuration must be rejected before a run starts.

Normal-envelope PASS requires all declared correctness and latency/drain criteria;
a missed normal target is NOT PASS even if recorded as a stress limit. Planned
stress saturation is distinct from silent loss, duplicate business records or
partial publication, which always fail correctness. Current full-history builds,
source snapshot replacement, window-materialized website extraction and one-host
resources are known potential bottlenecks, not preapproved reasons to skip checks.

## 6. Evidence, fixes and handoff

For each case capture: test run/scenario/config hash/seed, code and image IDs,
environment identity, start/end UTC, initial signatures, offered/actual workload,
fault trigger and stage state, scheduled DAG/run IDs, checkpoints, raw/work/attempt
references, manifest/batch/publication IDs, observations vs expected assertions,
resource samples, PASS/FAIL/NOT_RUN and failure reason, recovery actions, final
reconciliation, protected-environment check and teardown result. Runtime evidence
and secrets stay ignored; commit only sanitized finite fixture/test contracts and
selected safe evidence summaries. Do not dump expanded Compose/env or payload PII.

Classify findings: correctness/recovery bug, measurement/harness bug, performance
bottleneck, or source-contract limitation. Fix minimal causes within the selected
part; add regression before rerun. Stop for material semantic/architecture changes.
Keep an honest required-case matrix: an unsupported/deferred required case needs
explicit scope resolution, not a green total. STATUS records exact commands and
all checks not run. No automatic Git action or progression to the next part.

M09 packages the verified implementation, CI tiers and two demos after stability
acceptance; it does not invent proof for incomplete A-D cases or defer safety and
operator instructions needed to run them. These planned tests are local synthetic
evidence, not live-marketplace certification or an unspecified scale guarantee.
